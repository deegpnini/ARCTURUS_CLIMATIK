#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline de retreino com LOEO. Usa o backfill point-in-time (features novas).
"""

import sys
import json
from pathlib import Path

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

print("=" * 60)
print("PIPELINE DE RETREINO E LOEO — ARCTURUS CLIMATIK")
print("=" * 60)

# ---------------------------------------------------------------------------
# PASSO 1: Rodar o backfill point-in-time (features novas)
# ---------------------------------------------------------------------------
print("\n[1/4] Rodando backfill point-in-time (features novas)...")
import subprocess
result = subprocess.run([sys.executable, str(BASE / "backfill_features_pit.py")], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"[ERRO] Backfill falhou: {result.stderr}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# PASSO 2: Verificar se as features novas estão no dataset
# ---------------------------------------------------------------------------
print("\n[2/4] Verificando features no dataset...")
import pandas as pd
df = pd.read_parquet(BASE / "data" / "dataset_retreino.parquet")
print(f"Dataset: {len(df)} linhas, {len(df.columns)} colunas")

# Checagem de falha: as features novas DEVEM estar no dataset
features_esperadas = ["chuva_24h", "chuva_72h", "chuva_7d", "api_3d", "api_7d", "api_14d"]
faltando = [f for f in features_esperadas if f not in df.columns]
if faltando:
    print(f"[ERRO] Features faltando no dataset: {faltando}")
    print("O backfill não funcionou. Abortando.")
    sys.exit(1)
print(f"[OK] Features novas presentes: {features_esperadas}")

# ---------------------------------------------------------------------------
# PASSO 3: Retreinar o modelo v9
# ---------------------------------------------------------------------------
print("\n[3/4] Retreinando o modelo v9...")
import importlib.util
spec = importlib.util.spec_from_file_location("retreinar", BASE / "retreinar_modelo.py")
retreinar = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(retreinar)
    print("  [OK] Modelos v9 treinados")
except Exception as e:
    print(f"  [ERRO] Falha ao retreinar: {e}")
    sys.exit(1)

# ---------------------------------------------------------------------------
# PASSO 4: LOEO
# ---------------------------------------------------------------------------
print("\n[4/4] Rodando LOEO (Leave-One-Event-Out)...")
import numpy as np
import lightgbm as lgb
from sklearn.metrics import precision_recall_curve, auc

df = pd.read_parquet(BASE / "data" / "dataset_retreino.parquet")
df["timestamp"] = pd.to_datetime(df["timestamp"])
eventos = df["timestamp"].dt.date.unique()
print(f"  Eventos únicos: {len(eventos)}")

features_controle = ["timestamp", "horizonte", "y_true"]
features = [c for c in df.columns if c not in features_controle]

resultados_loeo = []

for h in ["1h", "3h", "6h"]:
    df_h = df[df["horizonte"] == h].copy()
    if len(df_h) < 30:
        print(f"  [AVISO] Dados insuficientes para {h} ({len(df_h)} linhas).")
        continue
    
    print(f"\n  === LOEO {h} ===")
    predicoes = []
    reais = []
    
    for evento in eventos:
        teste = df_h[df_h["timestamp"].dt.date == evento]
        treino = df_h[df_h["timestamp"].dt.date != evento]
        
        if len(teste) == 0 or len(treino) < 30:
            continue
        
        X_train = treino[features].fillna(0)
        y_train = treino["y_true"]
        X_test = teste[features].fillna(0)
        y_test = teste["y_true"]
        
        try:
            train_data = lgb.Dataset(X_train, label=y_train)
            params = {"objective": "regression", "metric": "mae", "num_leaves": 15, "verbose": -1}
            modelo = lgb.train(params, train_data, num_boost_round=50)
            y_pred = modelo.predict(X_test)
            predicoes.extend(y_pred)
            reais.extend(y_test.values)
        except Exception:
            continue
    
    if len(predicoes) > 10 and len(reais) == len(predicoes):
        reais_bin = [1 if r > 0 else 0 for r in reais]
        if sum(reais_bin) > 0:
            precision, recall, _ = precision_recall_curve(reais_bin, predicoes)
            pr_auc = auc(recall, precision)
            resultados_loeo.append((h, len(predicoes), pr_auc))
            print(f"  Amostras: {len(predicoes)}")
            print(f"  PR-AUC (LOEO): {pr_auc:.4f}")
        else:
            print(f"  [AVISO] Sem eventos positivos no LOEO de {h}.")

# Resumo final
print("\n" + "=" * 60)
print("RESUMO DO LOEO (v9 com features novas)")
print("=" * 60)
print(f"{'Horizonte':<10} | {'Amostras':<10} | {'PR-AUC (LOEO)'}")
print("-" * 40)
for h, n, pr_auc in resultados_loeo:
    print(f"{h:<10} | {n:<10} | {pr_auc:.4f}")

print("\nComparação com o v8 (PR-AUC ~0.63):")
for h, n, pr_auc in resultados_loeo:
    delta = pr_auc - 0.63
    status = "✅ MELHOR" if delta > 0.05 else "⚠️ PIOR" if delta < -0.05 else "➡️ IGUAL"
    print(f"  {h}: v9={pr_auc:.4f} | v8=0.63 | Delta={delta:+.4f} | {status}")

print("\n[OK] Pipeline concluído. Revise o LOEO antes de decidir.")
