#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Analisa o lag chuva-rio na série longa da ANA (Rio do Pouso)."""
import pandas as pd
from pathlib import Path

CSV_ANA = Path("data/ana_longa84580000.csv")
CSV_CHUVA = Path("data/chuva_bacia_openmeteo.csv")

print("=== ANALISANDO O PADRÃO DA ANA (SÉRIE LONGA) ===")

# 1. Carrega a cota da ANA (colunas: Data, Cota (m))
df_ana = pd.read_csv(CSV_ANA)
df_ana.columns = ["data", "cota_m"]  # Renomeia para facilitar
df_ana["data"] = pd.to_datetime(df_ana["data"])
df_ana["cota_cm"] = pd.to_numeric(df_ana["cota_m"], errors="coerce") * 100  # Converte para cm
df_ana = df_ana.set_index("data").sort_index()
print(f"ANA: {len(df_ana)} linhas (de {df_ana.index.min()} a {df_ana.index.max()})")

# 2. Carrega a chuva (Open-Meteo)
df_chuva = pd.read_csv(CSV_CHUVA, index_col=0, parse_dates=True)
df_chuva = df_chuva.mean(axis=1)  # média da bacia

# 3. Filtra o período que tem os dados de chuva (2023 a 2026)
inicio_comum = max(df_ana.index.min(), df_chuva.index.min())
fim_comum = min(df_ana.index.max(), df_chuva.index.max())
df_ana = df_ana[df_ana.index >= inicio_comum]
df_chuva = df_chuva[df_chuva.index >= inicio_comum]

# 4. Alinha as séries (mesma frequência)
df = pd.concat([df_ana["cota_cm"], df_chuva.rename("chuva")], axis=1).dropna()
print(f"Linhas alinhadas: {len(df)}")

if len(df) < 24:
    print("[AVISO] Poucas linhas alinhadas. O resultado pode ser instável.")
else:
    # 5. Correlação cruzada (lag)
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
