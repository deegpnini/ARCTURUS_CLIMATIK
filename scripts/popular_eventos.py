#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Detecta eventos (subida contínua) e popula a tabela assinatura_hidrologica."""

import psycopg2
import pandas as pd
from datetime import timedelta
from pathlib import Path

DB_URL = "postgresql:///arcturus"

LIMIAR_SUBIDA_CM = 50.0  # Subida total > 50 cm = evento
JANELA_H = 12             # Janela de 12h para o evento (subida + pico + recessão)

def detectar_eventos():
    """Detecta eventos (subida > 50 cm em até 12h)."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    cur.execute("""
        SELECT timestamp, cota_cm
        FROM leituras
        WHERE cota_cm IS NOT NULL AND qc = 'VALIDO'
        ORDER BY timestamp
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    df = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    eventos = []
    i = 0
    while i < len(df):
        cota_inicio = df.iloc[i]["cota_cm"]
        ts_inicio = df.iloc[i]["timestamp"]

        # Busca a cota 12h depois
        ts_fim = ts_inicio + timedelta(hours=JANELA_H)
        futuro = df[df["timestamp"] >= ts_fim]
        if len(futuro) == 0:
            break

        cota_fim = futuro.iloc[0]["cota_cm"]
        if cota_fim - cota_inicio > LIMIAR_SUBIDA_CM:
            # Evento detectado: pega a cota máxima na janela
            janela = df[(df["timestamp"] >= ts_inicio) & (df["timestamp"] <= ts_fim)]
            cota_max = janela["cota_cm"].max()
            idx_max = janela["cota_cm"].idxmax()
            ts_pico = janela.loc[idx_max, "timestamp"]

            evento_id = f"evento_{ts_inicio.strftime('%Y%m%d_%H%M')}"
            eventos.append({
                "evento_id": evento_id,
                "inicio": ts_inicio,
                "cota_inicio": cota_inicio,
                "pico": ts_pico,
                "cota_max": cota_max,
            })
            # Pula até o fim da janela (evita fragmentação)
            i = df[df["timestamp"] > ts_fim].index[0] if len(df[df["timestamp"] > ts_fim]) > 0 else len(df)
        else:
            i += 1

    return eventos

def popular_eventos(eventos):
    """Popula a tabela assinatura_hidrologica com os eventos detectados."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()

    for ev in eventos:
        # Puxa o Vz máximo na janela do evento
        ts_fim = ev["pico"] + timedelta(hours=2)
        cur.execute("""
            SELECT max(vz_cm_h)
            FROM leituras
            WHERE timestamp BETWEEN %s AND %s
              AND vz_cm_h IS NOT NULL AND qc = 'VALIDO'
        """, (ev["inicio"], ts_fim))
        row = cur.fetchone()
        vz_max = row[0] if row else None

        # Calcula o tempo até o pico (em horas)
        tempo_pico = (ev["pico"] - ev["inicio"]).total_seconds() / 3600

        # Insere na tabela
        cur.execute("""
            INSERT INTO assinatura_hidrologica (
                evento_id, tempo_ate_pico_h, cota_max_cm, vz_max_cm_h
            ) VALUES (%s, %s, %s, %s)
            ON CONFLICT (evento_id) DO NOTHING
        """, (ev["evento_id"], float(tempo_pico), float(ev["cota_max"]) if ev["cota_max"] is not None else None, float(vz_max) if vz_max is not None else None))

    conn.commit()
    cur.close()
    conn.close()
    print(f"[OK] {len(eventos)} eventos populados.")

if __name__ == "__main__":
    eventos = detectar_eventos()
    print(f"Eventos detectados: {len(eventos)}")
    for ev in eventos:
        print(f"  {ev['evento_id']} (início: {ev['inicio']}, cota: {ev['cota_inicio']}, pico: {ev['cota_max']} em {ev['pico']})")
    popular_eventos(eventos)
