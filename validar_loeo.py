#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Pipeline de validação LOEO (Leave-One-Event-Out).
Gate de produção: nenhum modelo é promovido sem passar no LOEO.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import precision_recall_curve, auc

BASE = Path(__file__).resolve().parent
DATASET = BASE / "data" / "dataset_retreino.parquet"
LOEO_DIR = BASE / "resultados" / "loeo"
HISTORICO = LOEO_DIR / "historico.csv"

# Regras de aprovação (por horizonte)
REGRAS = {
    "1h": {"pr_auc_min": 0.60},
    "3h": {"pr_auc_min": 0.60},
    "6h": {"pr_auc_min": 0.70},
}

# Modelo de produção atual (PR-AUC de referência)
PRODUCAO_REF = {
    "1h": 0.63,  # v8
    "3h": 0.63,  # v8
    "6h": 0.63,  # v8
}

def rodar_loeo(df, horizonte):
    """Roda o LOEO para um horizonte. Retorna o PR-AUC médio."""
    df_h = df[df["horizonte"] == horizonte].copy()
    if len(df_h) < 30:
        return None, 0
    
    df_h["timestamp"] = pd.to_datetime(df_h["timestamp"])
    eventos = df_h["timestamp"].dt.date.unique()
    
    features_controle = ["timestamp", "horizonte", "y_true"]
    features = [c for c in df_h.columns if c not in features_controle]
    
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
            return auc(recall, precision), len(predicoes)
    return None, 0

def main():
    print("=" * 60)
    print("VALIDAÇÃO LOEO — ARCTURUS CLIMATIK")
    print("=" * 60)
    
    df = pd.read_parquet(DATASET)
    print(f"Dataset: {len(df)} linhas\n")
    
    resultados = []
    for h in ["1h", "3h", "6h"]:
        print(f"=== LOEO {h} ===")
        pr_auc, n = rodar_loeo(df, h)
        
        if pr_auc is None:
            print(f"  ⚠️ Amostras insuficientes ({n})")
            resultados.append({"horizonte": h, "pr_auc": None, "status": "INCONCLUSIVO", "n": n})
            continue
        
        print(f"  PR-AUC: {pr_auc:.4f} (n={n})")
        ref = PRODUCAO_REF[h]
        delta = pr_auc - ref
        
        # Aplica as regras de aprovação
        if pr_auc < REGRAS[h]["pr_auc_min"]:
            status = "REPROVADO (abaixo do limiar)"
        elif delta <= 0:
            status = "REPROVADO (não superou produção)"
        else:
            status = "APROVADO"
        
        print(f"  Produção (v8): {ref:.4f} | Delta: {delta:+.4f}")
        print(f"  Status: {status}\n")
        
        resultados.append({"horizonte": h, "pr_auc": pr_auc, "ref": ref, "delta": delta, "status": status, "n": n})
    
    # Salva o relatório LOEO
    relatorio = {
        "data": datetime.now().isoformat(),
        "modelo": "v9",
        "resultados": resultados,
    }
    LOEO_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOEO_DIR / "loeo_v9.json", "w") as f:
        json.dump(relatorio, f, indent=2, default=str)
    print(f"[OK] Relatório salvo: {LOEO_DIR / 'loeo_v9.json'}")
    
    # Atualiza o histórico
    historico_existe = HISTORICO.exists()
    with open(HISTORICO, "a", newline="") as f:
        if not historico_existe:
            f.write("data,modelo,horizonte,pr_auc,ref,delta,status,n\n")
        for r in resultados:
            if r["pr_auc"] is not None:
                f.write(f"{datetime.now().date()},v9,{r['horizonte']},{r['pr_auc']:.4f},{r['ref']:.4f},{r['delta']:+.4f},{r['status']},{r['n']}\n")
    print(f"[OK] Histórico atualizado: {HISTORICO}")
    
    # Resumo final
    print("\n" + "=" * 60)
    print("RESUMO DO LOEO")
    print("=" * 60)
    aprovados = [r for r in resultados if r["status"] == "APROVADO"]
    reprovados = [r for r in resultados if r["status"].startswith("REPROVADO")]
    print(f"✅ Aprovados: {len(aprovados)} (horizontes: {', '.join(r['horizonte'] for r in aprovados) or 'nenhum'})")
    print(f"❌ Reprovados: {len(reprovados)} (horizontes: {', '.join(r['horizonte'] for r in reprovados) or 'nenhum'})")
    print(f"\nModelo v9: {'PROMOVIDO para ' + ', '.join(r['horizonte'] for r in aprovados) if aprovados else 'NÃO PROMOVIDO'}")

if __name__ == "__main__":
    main()
