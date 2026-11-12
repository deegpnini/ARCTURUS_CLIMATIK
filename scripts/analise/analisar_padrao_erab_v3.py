#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analisa o lag chuva-rio na ERAB usando a chuva da cabeceira (Anitápolis)."""
import pandas as pd
import psycopg2
from pathlib import Path

DB_URL = "postgresql:///arcturus"
CSV_CHUVA = Path("data/chuva_bacia_openmeteo.csv")

print("=== ANALISANDO O PADRÃO DA ERAB (CHUVA DA CABECEIRA) ===")

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

df_cota = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
df_cota["timestamp"] = pd.to_datetime(df_cota["timestamp"]).dt.floor("h")  # Arredonda para a hora cheia
df_cota = df_cota.set_index("timestamp").sort_index()
df_cota = df_cota.groupby("timestamp").mean()  # Média por hora (se houver mais de uma leitura)

# 2. Puxa a chuva (Open-Meteo) e filtra o mesmo período
df_chuva = pd.read_csv(CSV_CHUVA, index_col=0, parse_dates=True)
df_chuva = df_chuva[df_chuva.index >= '2026-11-01']
df_chuva = df_chuva[df_chuva.index <= pd.Timestamp.now()]

# Usa a chuva de Anitápolis (a cabeceira) e Tubarão (a foz)
# O CSV tem colunas: lauro_muller, orleans, grao_para, braco_norte, sao_ludgero, rio_fortuna, pedras_grandes, pouso
# Vamos usar a média dos pontos da cabeceira (lauro_muller, orleans, pouso)
chuva_cabeca = df_chuva[["lauro_muller", "orleans", "pouso"]].mean(axis=1)
chuva_foz = df_chuva["pouso"]  # Pouso é o ponto mais próximo de Tubarão

# 3. Alinha as séries
df = pd.concat([df_cota, chuva_cabeca.rename("chuva_cabeca"), chuva_foz.rename("chuva_foz")], axis=1).dropna()
print(f"Linhas alinhadas: {len(df)}")

if len(df) < 24:
    print("[AVISO] Poucas linhas alinhadas. O resultado pode ser instável.")
else:
    # 4. Correlação cruzada (lag) para a cabeceira
    print("\n=== CORRELAÇÃO CRUZADA (CHUVA CABECEIRA vs COTA) ===")
    print(f"{'Lag (h)':<10} | {'Correlação'}")
    print("-" * 25)
    
    max_lag = 0
    max_corr = -1
    for lag in range(0, 12):
        corr = df["chuva_cabeca"].corr(df["cota_cm"].shift(-lag))
        print(f"{lag:<10} | {corr:.4f}")
        if corr > max_corr:
            max_corr = corr
            max_lag = lag
    
    print(f"\n[OK] Lag de maior correlação (cabeceira): {max_lag} horas (corr = {max_corr:.4f})")
    
    # 5. Correlação cruzada (lag) para a foz
    print("\n=== CORRELAÇÃO CRUZADA (CHUVA FOZ vs COTA) ===")
    print(f"{'Lag (h)':<10} | {'Correlação'}")
    print("-" * 25)
    
    max_lag_foz = 0
    max_corr_foz = -1
    for lag in range(0, 12):
        corr = df["chuva_foz"].corr(df["cota_cm"].shift(-lag))
        print(f"{lag:<10} | {corr:.4f}")
        if corr > max_corr_foz:
            max_corr_foz = corr
            max_lag_foz = lag
    
    print(f"\n[OK] Lag de maior correlação (foz): {max_lag_foz} horas (corr = {max_corr_foz:.4f})")
