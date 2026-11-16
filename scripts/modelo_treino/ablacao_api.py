#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Ablação: v8 (27 features) vs v8+API (33 features), mesmos folds.
Mede o efeito real do API, separado da mudança de dados.
"""

import json
import sys
from pathlib import Path

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import precision_recall_curve, auc

BASE = Path(__file__).resolve().parent
DATASET = BASE / "data" / "dataset_retreino.parquet"

df = pd.read_parquet(DATASET)
df["timestamp"] = pd.to_datetime(df["timestamp"])

# Features antigas (v8) e novas (API + chuva)
features_antigas = [
    "cota", "cota_lag_15m", "cota_lag_30m", "cota_lag_60m",
    "cota_lag_180m", "cota_lag_360m", "cota_lag_720m", "cota_lag_1440m",
    "delta_15m", "delta_60m", "aceleracao_1h", "sin_hora", "cos_hora",
    "sin_dia_ano", "cos_dia_ano", "delta_180m", "cota_std_12h",
    "cota_max_12h", "cota_min_12h",
    "bacia_lag_4h", "bacia_lag_6h", "bacia_lag_8h",
    "bacia_3h", "bacia_6h", "bacia_12h", "bacia_max1h", "bacia_pontos_forte",
]
features_novas = ["chuva_24h", "chuva_72h", "chuva_7d", "api_3d", "api_7d", "api_14d"]

eventos = df["timestamp"].dt.date.unique()
print(f"Total de linhas: {len(df)}")
print(f"Eventos únicos: {len(eventos)}")

def rodar_loeo(df, features, horizonte, eventos):
    """Roda o LOEO para um conjunto de features e um horizonte."""
    df_h = df[df["horizonte"] == horizonte].copy()
    if len(df_h) < 30:
        return None
    
    predicoes = []
    reais = []
    folds = []
    
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
            
            reais_bin = (y_test > 0).astype(int)
            if reais_bin.sum() > 0:
                precision, recall, _ = precision_recall_curve(reais_bin, y_pred)
                pr_auc = auc(recall, precision)
                folds.append(pr_auc)
        except Exception:
            continue
    
    if folds:
        return {"folds": folds, "media": np.mean(folds), "desvio": np.std(folds)}
    return None

print("\n" + "=" * 60)
print("ABLAÇÃO: v8 (27 features) vs v8+API (33 features)")
print("=" * 60)

for h in ["1h", "3h", "6h"]:
    print(f"\n=== Horizonte {h} ===")
    
    # A: só features antigas
    resultado_a = rodar_loeo(df, features_antigas, h, eventos)
    # B: features antigas + API
    resultado_b = rodar_loeo(df, features_antigas + features_novas, h, eventos)
    
    if resultado_a is None or resultado_b is None:
        print(f"  [AVISO] Dados insuficientes para {h}.")
        continue
    
    print(f"  A (v8, 27 feats):")
    print(f"    Folds: {[f'{x:.4f}' for x in resultado_a['folds']]}")
    print(f"    Média: {resultado_a['media']:.4f} | Desvio: {resultado_a['desvio']:.4f}")
    
    print(f"  B (v8+API, 33 feats):")
    print(f"    Folds: {[f'{x:.4f}' for x in resultado_b['folds']]}")
    print(f"    Média: {resultado_b['media']:.4f} | Desvio: {resultado_b['desvio']:.4f}")
    
    delta = resultado_b['media'] - resultado_a['media']
    print(f"  Delta (B - A): {delta:+.4f}")
    
    # Critério: B > A em pelo menos 3 de 4 folds
    if len(resultado_a["folds"]) == len(resultado_b["folds"]):
        vitorias = sum(1 for a, b in zip(resultado_a["folds"], resultado_b["folds"]) if b > a)
        print(f"  Folds onde B > A: {vitorias}/{len(resultado_a['folds'])}")

# Importância das features API no modelo B (6h)
print("\n" + "=" * 60)
print("IMPORTÂNCIA DAS FEATURES API (6h)")
print("=" * 60)
df_6h = df[df["horizonte"] == "6h"]
if len(df_6h) > 30:
    X = df_6h[features_antigas + features_novas].fillna(0)
    y = df_6h["y_true"]
    train_data = lgb.Dataset(X, label=y)
    modelo = lgb.train({"objective": "regression", "verbose": -1}, train_data, num_boost_round=50)
    importancias = modelo.feature_importance(importance_type="gain")
    nomes = modelo.feature_name()
    df_imp = pd.DataFrame({"feature": nomes, "importance": importancias}).sort_values("importance", ascending=False)
    print(df_imp.head(15).to_string(index=False))
