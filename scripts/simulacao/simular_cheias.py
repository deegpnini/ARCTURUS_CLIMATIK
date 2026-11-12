#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Gera cheias sintéticas (perturbação da chuva real) para treinar o v11."""

import pandas as pd
import numpy as np
from pathlib import Path

BASE = Path(__file__).resolve().parent
DATASET = BASE / "data" / "dataset_retreino.parquet"
OUT = BASE / "data" / "dataset_retreino_com_sinteticos.parquet"

print("=== SIMULANDO CHEIAS SINTÉTICAS ===")

# 1. Carrega o dataset real
df = pd.read_parquet(DATASET)
print(f"Dataset real: {len(df)} linhas")

# 2. Identifica a cheia real (04/11)
cheia_real = df[(df["timestamp"] >= "2026-11-04") & (df["timestamp"] <= "2026-11-05")]
print(f"Linhas da cheia real: {len(cheia_real)}")

if len(cheia_real) == 0:
    print("[ERRO] Cheia real não encontrada no dataset.")
    exit(1)

# 3. Gera 5 versões sintéticas (variações da chuva)
sinteticos = []
for i, fator in enumerate([0.8, 0.9, 1.1, 1.2, 1.3]):
    cheia_sint = cheia_real.copy()
    # Perturba a chuva (colunas que começam com "chuva_")
    for col in cheia_sint.columns:
        if col.startswith("chuva_") or col.startswith("bacia_") or col.startswith("api_"):
            cheia_sint[col] = cheia_sint[col] * fator
    # Perturba o y_true (variação da cota) proporcionalmente
    cheia_sint["y_true"] = cheia_sint["y_true"] * fator
    cheia_sint["timestamp"] = cheia_sint["timestamp"] + pd.Timedelta(days=i+1)
    sinteticos.append(cheia_sint)
    print(f"  Sintético {i+1}: fator {fator} ({len(cheia_sint)} linhas)")

# 4. Junta real + sintéticos
df_novo = pd.concat([df] + sinteticos, ignore_index=True)
df_novo.to_parquet(OUT)
print(f"\n[OK] Dataset com sintéticos: {len(df_novo)} linhas (real + {len(sinteticos)} sintéticos)")
