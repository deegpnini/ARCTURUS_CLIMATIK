#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Retreina o modelo v10 com o evento de 04/11 (cheia).
O backfill point-in-time garante que as features usam apenas dados até o timestamp.
"""

import sys
import json
import subprocess
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

print("=" * 60)
print("RETREINO v10 — INCLUINDO O EVENTO DE 04/11 (CHEIA)")
print("=" * 60)

# 1. Rodar o backfill point-in-time (atualiza o dataset)
print("\n[1/3] Rodando backfill point-in-time...")
result = subprocess.run([sys.executable, str(BASE / "backfill_features_pit.py")], capture_output=True, text=True)
print(result.stdout)
if result.returncode != 0:
    print(f"[ERRO] Backfill falhou: {result.stderr}")
    sys.exit(1)

# 2. Verificar se o evento de 04/11 está no dataset
print("\n[2/3] Verificando o evento de 04/11...")
import pandas as pd
df = pd.read_parquet(BASE / "data" / "dataset_retreino.parquet")
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Conta as linhas do evento de 04/11
evento_04_11 = df[df["timestamp"].dt.date == pd.Timestamp("2026-11-04").date()]
print(f"Linhas do evento 04/11: {len(evento_04_11)}")
if len(evento_04_11) == 0:
    print("[AVISO] O evento de 04/11 não está no dataset. O backfill pode ter falhado.")
else:
    print(f"Cota máxima no evento: {evento_04_11['y_true'].max():.1f} cm")
    print(f"Cota mínima no evento: {evento_04_11['y_true'].min():.1f} cm")

# 3. Retreinar o modelo v10 (com os modelos novos)
print("\n[3/3] Retreinando o modelo v10...")
import importlib.util
spec = importlib.util.spec_from_file_location("retreinar", BASE / "retreinar_modelo.py")
retreinar = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(retreinar)
    print("  [OK] Modelos v10 treinados")
except Exception as e:
    print(f"  [ERRO] Falha ao retreinar: {e}")
    sys.exit(1)

# 4. Rodar o LOEO (para validar o v10)
print("\n[4/4] Rodando LOEO (Leave-One-Event-Out) para o v10...")
import numpy as np
import lightgbm as lgb
from sklearn.metrics import precision_recall_curve, auc

df = pd.read_parquet(BASE / "data" / "dataset_retreino.parquet")
df["timestamp"] = pd.to_datetime(df["timestamp"])
eventos = df["timestamp"].dt.date.unique()
print(f"Eventos únicos: {len(eventos)}")

features_controle = ["timestamp", "horizonte", "y_true"]
features = [c for c in df.columns if c not in features_controle]

resultados_loeo = []
for h in ["1h", "3h", "6h"]:
    df_h = df[df["horizonte"] == h].copy()
    if len(df_h) < 30:
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

print("\n" + "=" * 60)
print("RESUMO DO LOEO (v10 com o evento de 04/11)")
print("=" * 60)
print(f"{'Horizonte':<10} | {'Amostras':<10} | {'PR-AUC (LOEO)'}")
print("-" * 40)
for h, n, pr_auc in resultados_loeo:
    print(f"{h:<10} | {n:<10} | {pr_auc:.4f}")

print("\nComparação com o v8 (PR-AUC ~0.63):")
for h, n, pr_auc in resultados_loeo:
    delta = pr_auc - 0.63
    status = "✅ MELHOR" if delta > 0.05 else "⚠️ PIOR" if delta < -0.05 else "➡️ IGUAL"
    print(f"  {h}: v10={pr_auc:.4f} | v8=0.63 | Delta={delta:+.4f} | {status}")
