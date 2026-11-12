#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analisa o padrão de lag chuva-rio na ANA (antes da descontinuação)."""
import pandas as pd
import numpy as np
import psycopg2
from pathlib import Path

DB_URL = "postgresql:///arcturus"
CSV_CHUVA = Path("data/chuva_bacia_openmeteo.csv")

print("=== ANALISANDO O PADRÃO DA ANA (LAG CHUVA-RIO) ===")

# 1. Puxa a cota histórica da ANA (Rio do Pouso) do banco
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT timestamp, cota_cm
    FROM leituras
    WHERE cota_cm IS NOT NULL
    ORDER BY timestamp
""")
rows = cur.fetchall()
cur.close()
conn.close()

if not rows:
    print("[ERRO] Sem dados de cota no banco.")
    exit(1)

df_cota = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
df_cota["timestamp"] = pd.to_datetime(df_cota["timestamp"])
df_cota = df_cota.set_index("timestamp").sort_index()

# 2. Puxa a chuva (Open-Meteo)
if not CSV_CHUVA.exists():
    print("[ERRO] CSV de chuva não encontrado.")
    exit(1)

df_chuva = pd.read_csv(CSV_CHUVA, index_col=0, parse_dates=True)
df_chuva = df_chuva[df_chuva.index <= pd.Timestamp.now()]
df_chuva = df_chuva.mean(axis=1)  # média da bacia

# 3. Alinha as séries (mesma frequência)
df = pd.concat([df_cota, df_chuva.rename("chuva")], axis=1).dropna()
print(f"Linhas alinhadas: {len(df)}")

# 4. Calcula a correlação cruzada (lag entre chuva e cota)
# O lag é o número de horas que a chuva leva para fazer a cota subir
print("\n=== CORRELAÇÃO CRUZADA (LAG CHUVA-RIO) ===")
print(f"{'Lag (h)':<10} | {'Correlação'}")
print("-" * 25)

for lag in range(0, 24):
    # Correlação entre a chuva (t) e a cota (t + lag)
    corr = df["chuva"].corr(df["cota_cm"].shift(-lag))
    print(f"{lag:<10} | {corr:.4f}")

# 5. Identifica o lag de maior correlação
max_lag = 0
max_corr = -1
for lag in range(0, 24):
    corr = df["chuva"].corr(df["cota_cm"].shift(-lag))
    if corr > max_corr:
        max_corr = corr
        max_lag = lag

print(f"\n[OK] Lag de maior correlação: {max_lag} horas (corr = {max_corr:.4f})")
print(f"Isso significa que a chuva leva ~{max_lag} horas para fazer a cota subir.")
