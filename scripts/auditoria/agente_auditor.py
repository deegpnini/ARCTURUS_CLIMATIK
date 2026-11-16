#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGENTE AUDITOR: Valida o dataset do Guardião antes do treino."""

import sys
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
IN_PARQUET = BASE / "data" / "dataset_retreino.parquet"

print("[AUDITOR] Iniciando auditoria do dataset...")

if not IN_PARQUET.exists():
    print("[ERRO] Dataset não encontrado.")
    sys.exit(1)

df = pd.read_parquet(IN_PARQUET)
print(f"Total de linhas: {len(df)}")
print(f"Total de colunas: {len(df.columns)}")

erros = []
eventos_extremos = []

# Regra 1: Cota nunca pode ser negativa
if "cota" in df.columns:
    if (df["cota"] < 0).any():
        erros.append("Cota negativa detectada (impossível fisicamente).")

# Regra 2: Classificar variações (ERRO vs EVENTO_EXTREMO)
# taxa_max = 80 cm/15 min (baseado na cheia de 04/11, documentado no protocolo)
LIMITE_FISICO_CM_15MIN = 80

for h in ["1h", "3h", "6h"]:
    df_h = df[df["horizonte"] == h].sort_values("timestamp").copy()
    if len(df_h) == 0:
        continue

    df_h["delta_tempo"] = df_h["timestamp"].diff().dt.total_seconds() / 900
    df_h["taxa_15min"] = df_h["cota"].diff() / df_h["delta_tempo"]

    # ERRO: taxa > limite físico (80 cm/15 min)
    erros_fisicos = df_h[df_h["taxa_15min"].abs() > LIMITE_FISICO_CM_15MIN]
    if len(erros_fisicos) > 0:
        erros.append(f"ERRO: {len(erros_fisicos)} leituras com taxa > {LIMITE_FISICO_CM_15MIN} cm/15 min no {h}.")

    # EVENTO_EXTREMO: variação > 150/200 cm, mas taxa fisicamente possível
    limite_var = {"1h": 100, "3h": 150, "6h": 200}[h]
    eventos_extremos_h = df_h[(df_h["y_true"].abs() > limite_var) & (df_h["taxa_15min"].abs() <= LIMITE_FISICO_CM_15MIN)]
    if len(eventos_extremos_h) > 0:
        eventos_extremos.append(f"EVENTO_EXTREMO: {len(eventos_extremos_h)} linhas no {h} (variação > {limite_var} cm, mas taxa fisicamente possível).")

# Regra 3: Nulos (exceto Vz/Az)
colunas_vz = ["delta_15m", "delta_60m", "aceleracao_1h"]
df_sem_vz = df.drop(columns=[c for c in colunas_vz if c in df.columns])
if df_sem_vz.isnull().values.any():
    nulos = df_sem_vz.isnull().sum()
    colunas_com_nulos = nulos[nulos > 0].index.tolist()
    erros.append(f"Nulos detectados: {colunas_com_nulos[:5]}...")

# Resultado
if erros:
    print("\n❌ [AUDITOR] REPROVADO. Erros encontrados:")
    for e in erros:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\n✅ [AUDITOR] APROVADO.")
    if eventos_extremos:
        print("\n⚠️ EVENTOS EXTREMOS (revisão humana recomendada):")
        for e in eventos_extremos:
            print(f"  - {e}")
    else:
        print("  Nenhum evento extremo detectado.")
    sys.exit(0)
