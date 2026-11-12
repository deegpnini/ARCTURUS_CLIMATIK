#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mede o lag chuva-rio para cada evento da tabela assinatura_hidrologica."""

import psycopg2
import pandas as pd
from pathlib import Path
from datetime import timedelta

DB_URL = "postgresql:///arcturus"
CSV_CHUVA = Path("data/chuva_bacia_openmeteo.csv")

# Carrega a chuva (Open-Meteo)
df_chuva = pd.read_csv(CSV_CHUVA, index_col=0, parse_dates=True)
df_chuva = df_chuva[["orleans", "lauro_muller", "braco_norte"]]  # cabeceira
df_chuva["media_cabeca"] = df_chuva.mean(axis=1)

# Conecta ao banco
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Puxa os eventos
cur.execute("""
    SELECT evento_id, tempo_ate_pico_h, cota_max_cm
    FROM assinatura_hidrologica
    ORDER BY evento_id
""")
eventos = cur.fetchall()

print("=== LAG CHUVA-RIO POR EVENTO ===")
print(f"{'Evento':<30} | {'Pico da Chuva':<20} | {'Lag (h)':<10}")
print("-" * 65)

for evento_id, tempo_pico, cota_max in eventos:
    # Puxa o timestamp de início do evento (a partir do evento_id)
    # Ex: evento_20261104_0830 -> 2026-11-04 08:30
    try:
        ts_str = evento_id.replace("evento_", "")
        ts_inicio = pd.Timestamp(ts_str[:8] + " " + ts_str[9:11] + ":" + ts_str[11:13])
    except Exception:
        continue

    # Puxa a chuva nas 24h antes do início da subida
    ts_antes = ts_inicio - timedelta(hours=24)
    chuva_janela = df_chuva[(df_chuva.index >= ts_antes) & (df_chuva.index <= ts_inicio)]
    if len(chuva_janela) == 0:
        continue

    # Pico da chuva (hora em que a chuva foi mais forte)
    idx_pico_chuva = chuva_janela["media_cabeca"].idxmax()
    pico_chuva = chuva_janela.loc[idx_pico_chuva, "media_cabeca"]

    # Lag (tempo entre o pico da chuva e o pico da cota)
    lag = (ts_inicio + timedelta(hours=tempo_pico) - idx_pico_chuva).total_seconds() / 3600

    print(f"{evento_id:<30} | {idx_pico_chuva.strftime('%d/%m %H:%M'):<20} | {lag:<10.1f}")

cur.close()
conn.close()
