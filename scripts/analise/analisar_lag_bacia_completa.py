#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analisa o lag de cada ponto da bacia até a ERAB (Tubarão)."""
import pandas as pd
import psycopg2
from pathlib import Path

DB_URL = "postgresql:///arcturus"
CSV_CHUVA = Path("data/chuva_bacia_openmeteo.csv")

print("=== ANÁLISE DE LAG POR PONTO DA BACIA ===")

# 1. Puxa a cota da ERAB
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT timestamp, cota_cm FROM leituras
    WHERE cota_cm IS NOT NULL AND timestamp >= '2026-11-01'
    ORDER BY timestamp
""")
rows = cur.fetchall()
cur.close()
conn.close()

df_cota = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
df_cota["timestamp"] = pd.to_datetime(df_cota["timestamp"]).dt.floor("h")
df_cota = df_cota.set_index("timestamp").sort_index()
df_cota = df_cota.groupby("timestamp").mean()

# 2. Puxa a chuva
df_chuva = pd.read_csv(CSV_CHUVA, index_col=0, parse_dates=True)
df_chuva = df_chuva[df_chuva.index >= '2026-11-01']
df_chuva = df_chuva[df_chuva.index <= pd.Timestamp.now()]

# 3. Testa cada ponto
pontos = {
    "lauro_muller": "Cabeceira (Lauro Müller)",
    "orleans": "Cabeceira (Orleans)",
    "pouso": "Meio (Rio do Pouso)",
    "braco_norte": "Meio (Braço do Norte)",
    "sao_ludgero": "Meio (São Ludgero)",
    "rio_fortuna": "Meio (Rio Fortuna)",
    "pedras_grandes": "Jusante (Pedras Grandes)",
    "grao_para": "Jusante (Grão Pará)",
}

print("\n" + "=" * 60)
print("LAG DE MAIOR CORRELAÇÃO POR PONTO DA BACIA")
print("=" * 60)
print(f"{'Ponto':<30} | {'Lag (h)':<10} | {'Correlação'}")
print("-" * 60)

for col, nome in pontos.items():
    if col not in df_chuva.columns:
        print(f"{nome:<30} | [COLUNA NÃO ENCONTRADA]")
        continue
    
    df = pd.concat([df_cota, df_chuva[col].rename("chuva")], axis=1).dropna()
    if len(df) < 24:
        print(f"{nome:<30} | [POUCOS DADOS]")
        continue
    
    max_lag = 0
    max_corr = -1
    for lag in range(0, 24):
        corr = df["chuva"].corr(df["cota_cm"].shift(-lag))
        if corr > max_corr:
            max_corr = corr
            max_lag = lag
    
    print(f"{nome:<30} | {max_lag:<10} | {max_corr:.4f}")

print("\n[OK] Análise concluída.")
print("O ponto com maior lag é o que mais demora a chegar na ERAB.")
