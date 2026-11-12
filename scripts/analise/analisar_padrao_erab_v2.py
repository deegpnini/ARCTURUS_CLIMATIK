#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analisa o lag chuva-rio na ERAB (série curta)."""
import pandas as pd
import psycopg2
from pathlib import Path

DB_URL = "postgresql:///arcturus"
CSV_CHUVA = Path("data/chuva_bacia_openmeteo.csv")

print("=== ANALISANDO O PADRÃO DA ERAB (SÉRIE CURTA) ===")

# 1. Puxa a cota da ERAB (do banco)
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT timestamp, cota_cm
    FROM leituras
    WHERE cota_cm IS NOT NULL
      AND timestamp >= '2026-11-01'
    ORDER BY timestamp
""")
rows = cur.fetchall()
cur.close()
conn.close()

if not rows:
    print("[ERRO] Sem dados de cota no banco (ERAB).")
    exit(1)

df_cota = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
df_cota["timestamp"] = pd.to_datetime(df_cota["timestamp"])
df_cota = df_cota.set_index("timestamp").sort_index()

# 2. Puxa a chuva (Open-Meteo) e filtra o mesmo período
df_chuva = pd.read_csv(CSV_CHUVA, index_col=0, parse_dates=True)
df_chuva = df_chuva[df_chuva.index >= '2026-11-01']
df_chuva = df_chuva[df_chuva.index <= pd.Timestamp.now()]
df_chuva = df_chuva.mean(axis=1)  # média da bacia

# 3. Alinha as séries (mesma frequência)
df = pd.concat([df_cota, df_chuva.rename("chuva")], axis=1).dropna()
print(f"Linhas alinhadas: {len(df)}")

if len(df) < 24:
    print("[AVISO] Poucas linhas alinhadas. O resultado pode ser instável.")
else:
    # 4. Correlação cruzada (lag)
    print("\n=== CORRELAÇÃO CRUZADA (LAG CHUVA-RIO) ===")
    print(f"{'Lag (h)':<10} | {'Correlação'}")
    print("-" * 25)
    
    max_lag = 0
    max_corr = -1
    for lag in range(0, 12):
        corr = df["chuva"].corr(df["cota_cm"].shift(-lag))
        print(f"{lag:<10} | {corr:.4f}")
        if corr > max_corr:
            max_corr = corr
            max_lag = lag
    
    print(f"\n[OK] Lag de maior correlação: {max_lag} horas (corr = {max_corr:.4f})")
