#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analisa o lag chuva-rio na série longa da ANA (Rio do Pouso)."""
import pandas as pd
from pathlib import Path

CSV_ANA = Path("data/ana_longa84580000.csv")
CSV_CHUVA = Path("data/chuva_bacia_openmeteo.csv")

print("=== ANALISANDO O LAG CHUVA-RIO NA ANA (SÉRIE LONGA) ===")

# 1. Carrega a cota da ANA
df_ana = pd.read_csv(CSV_ANA)
print(f"Colunas da ANA: {list(df_ana.columns)}")
print(f"Primeiras linhas:\n{df_ana.head()}")

# 2. Carrega a chuva (Open-Meteo)
df_chuva = pd.read_csv(CSV_CHUVA, index_col=0, parse_dates=True)
df_chuva = df_chuva.mean(axis=1)  # média da bacia

# 3. Alinha as séries (mesma frequência)
# (Ajustar o nome da coluna de timestamp da ANA, se necessário)
# Aqui, assumimos que a ANA tem uma coluna "timestamp" e "cota_cm"
if "timestamp" in df_ana.columns and "cota_cm" in df_ana.columns:
    df_ana["timestamp"] = pd.to_datetime(df_ana["timestamp"])
    df_ana = df_ana.set_index("timestamp").sort_index()
    df = pd.concat([df_ana["cota_cm"], df_chuva.rename("chuva")], axis=1).dropna()
    print(f"\nLinhas alinhadas: {len(df)}")
    
    if len(df) < 24:
        print("[AVISO] Poucas linhas alinhadas. O resultado pode ser instável.")
    else:
        # 4. Correlação cruzada (lag)
        print("\n=== CORRELAÇÃO CRUZADA (LAG CHUVA-RIO) ===")
        print(f"{'Lag (h)':<10} | {'Correlação'}")
        print("-" * 25)
        
        max_lag = 0
        max_corr = -1
        for lag in range(0, 24):
            corr = df["chuva"].corr(df["cota_cm"].shift(-lag))
            print(f"{lag:<10} | {corr:.4f}")
            if corr > max_corr:
                max_corr = corr
                max_lag = lag
        
        print(f"\n[OK] Lag de maior correlação: {max_lag} horas (corr = {max_corr:.4f})")
        print(f"Isso significa que a chuva leva ~{max_lag} horas para fazer a cota subir.")
else:
    print("[ERRO] O CSV da ANA não tem as colunas 'timestamp' e 'cota_cm'.")
