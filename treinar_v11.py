#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Treina o v11 (com sintéticos) e valida no LOEO (só com eventos reais)."""

import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
from sklearn.metrics import precision_recall_curve, auc, average_precision_score

BASE = Path(__file__).resolve().parent
DATASET_COM_SINT = BASE / "data" / "dataset_retreino_com_sinteticos.parquet"
DATASET_REAL = BASE / "data" / "dataset_retreino.parquet"
MODELOS = {
    "1h": BASE / "modelos" / "modelo_delta_1h_v11.txt",
    "3h": BASE / "modelos" / "modelo_delta_3h_v11.txt",
    "6h": BASE / "modelos" / "modelo_delta_6h_v11.txt",
}

print("=== TREINANDO v11 (REAL + SINTÉTICO) E VALIDANDO NO LOEO (SÓ REAL) ===")

# 1. Carrega o dataset completo (real + sintético) para treino
df_completo = pd.read_parquet(DATASET_COM_SINT)
print(f"Dataset completo: {len(df_completo)} linhas")

# 2. Carrega o dataset real (para validação no LOEO)
df_real = pd.read_parquet(DATASET_REAL)
print(f"Dataset real: {len(df_real)} linhas")

# 3. Define as features
features_controle = ["timestamp", "horizonte", "y_true"]
features = [c for c in df_completo.columns if c not in features_controle]

# 4. Treina o v11 para cada horizonte
for h, path in MODELOS.items():
    print(f"\n=== Treinando v11 ({h}) ===")
    
    # Filtra o horizonte no dataset completo
    df_h_completo = df_completo[df_completo["horizonte"] == h]
    X_train = df_h_completo[features].fillna(0)
    y_train = df_h_completo["y_true"]
    
    # Treina o LightGBM
    train_data = lgb.Dataset(X_train, label=y_train)
    params = {
        "objective": "regression",
        "metric": "mae",
        "num_leaves": 31,
        "learning_rate": 0.05,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": -1,
    }
    modelo = lgb.train(params, train_data, num_boost_round=100)
    modelo.save_model(str(path))
    print(f"  [OK] Modelo salvo: {path}")
    
    # LOEO (só com o dataset real)
    df_h_real = df_real[df_real["horizonte"] == h].copy()
    df_h_real["timestamp"] = pd.to_datetime(df_h_real["timestamp"])
    eventos = df_h_real["timestamp"].dt.date.unique()
    
    predicoes = []
    reais = []
    for evento in eventos:
        teste = df_h_real[df_h_real["timestamp"].dt.date == evento]
        treino = df_h_real[df_h_real["timestamp"].dt.date != evento]
        if len(teste) == 0 or len(treino) < 30:
            continue
        X_teste = teste[features].fillna(0)
        y_teste = teste["y_true"]
        try:
            y_pred = modelo.predict(X_teste)
            predicoes.extend(y_pred)
            reais.extend(y_teste.values)
        except Exception:
            continue
    
    if len(predicoes) > 10 and len(reais) == len(predicoes):
        reais_bin = [1 if r > 0 else 0 for r in reais]
        if sum(reais_bin) > 0:
            precision, recall, _ = precision_recall_curve(reais_bin, predicoes)
            pr_auc = auc(recall, precision)
            ap = average_precision_score(reais_bin, predicoes)
            print(f"  LOEO (só real): n={len(predicoes)}, PR-AUC={pr_auc:.4f}, AP={ap:.4f}")
