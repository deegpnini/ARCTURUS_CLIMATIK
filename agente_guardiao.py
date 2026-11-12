#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGENTE GUARDIÃO: Monta o dataset point-in-time com o y_true correto."""
import pandas as pd
import psycopg2
import sys
from pathlib import Path
from datetime import timedelta

BASE = Path(__file__).resolve().parent
DB_URL = "postgresql:///arcturus"
OUT_CSV = BASE / "data" / "dataset_bruto_para_auditoria.csv"

print("[GUARDIÃO] Iniciando montagem do dataset...")

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Puxa todas as leituras (cota)
cur.execute("SELECT timestamp, cota_cm FROM leituras WHERE cota_cm IS NOT NULL ORDER BY timestamp")
rows = cur.fetchall()
cur.close()
conn.close()

if not rows:
    print("[ERRO] Sem dados no banco.")
    sys.exit(1)

df_leituras = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
df_leituras["timestamp"] = pd.to_datetime(df_leituras["timestamp"])
df_leituras = df_leituras.set_index("timestamp").sort_index()

dados = []
horizontes = {"1h": 1, "3h": 3, "6h": 6}

for i in range(len(df_leituras) - 24): # Garante 6h de futuro
    ts_atual = df_leituras.index[i]
    cota_atual = df_leituras.iloc[i]["cota_cm"]
    
    for h_nome, h_horas in horizontes.items():
        ts_futuro = ts_atual + timedelta(hours=h_horas)
        
        # Busca a cota futura (a leitura mais próxima do alvo)
        df_futuro = df_leituras[df_leituras.index >= ts_futuro]
        if len(df_futuro) == 0: continue
        
        cota_futura = df_futuro.iloc[0]["cota_cm"]
        
        # O ALVO CORRETO: variação da cota
        y_true = cota_futura - cota_atual
        
        dados.append({
            "timestamp_origem": ts_atual,
            "horizonte": h_nome,
            "cota_origem": cota_atual,
            "cota_futura": cota_futura,
            "y_true": y_true
        })

df_dataset = pd.DataFrame(dados)
df_dataset.to_csv(OUT_CSV, index=False)
print(f"[GUARDIÃO] Dataset bruto salvo: {OUT_CSV} ({len(df_dataset)} linhas)")
print("[GUARDIÃO] Aguardando auditoria...")
