#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Retreina o LightGBM com as features novas (chuva acumulada 24h, 72h, 7d)."""

import json
import lightgbm as lgb
import pandas as pd
import numpy as np
from pathlib import Path
from sklearn.model_selection import train_test_split
from sklearn.metrics import precision_recall_curve, auc

BASE = Path(__file__).resolve().parent
DATASET = BASE / "data" / "dataset_retreino.parquet"
MODELOS_NOVOS = {
    "1h": BASE / "modelos" / "modelo_delta_1h_v9.txt",
    "3h": BASE / "modelos" / "modelo_delta_3h_v9.txt",
    "6h": BASE / "modelos" / "modelo_delta_6h_v9.txt",
}

# Carrega o dataset
df = pd.read_parquet(DATASET)
print(f"Dataset: {len(df)} linhas, {len(df.columns)} colunas")

# Lista de features (exclui as colunas de controle)
features_controle = ["timestamp", "horizonte", "y_true"]
features = [c for c in df.columns if c not in features_controle]
print(f"Features: {len(features)}")

# Treina um modelo para cada horizonte
for h, path_novo in MODELOS_NOVOS.items():
    print(f"\n=== Treinando {h} ===")
    
    df_h = df[df["horizonte"] == h].copy()
    if len(df_h) < 30:
        print(f"[AVISO] Dados insuficientes para {h} ({len(df_h)} linhas). Pulando.")
        continue
    
    X = df_h[features].fillna(0)
    y = df_h["y_true"]
    
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    
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
    
    y_pred = modelo.predict(X_test)
    mae = np.mean(np.abs(y_test - y_pred))
    print(f"MAE no teste: {mae:.2f} cm")
    
    y_test_bin = (y_test > 0).astype(int)
    if y_test_bin.sum() > 0:
        precision, recall, _ = precision_recall_curve(y_test_bin, y_pred)
        pr_auc = auc(recall, precision)
        print(f"PR-AUC: {pr_auc:.4f}")
    
    modelo.save_model(str(path_novo))
    print(f"[OK] Modelo salvo: {path_novo}")
