#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import precision_recall_curve, average_precision_score, precision_score, recall_score, f1_score

OUT_DIR = "resultados"
PRED_PATH = "resultados/historico_previsoes.csv"
THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

def carregar_predicoes():
    df = pd.read_csv(PRED_PATH)
    print(f"[OK] {len(df)} linhas carregadas de {PRED_PATH}")
    print(f"[INFO] Colunas: {list(df.columns)}")
    cols = {c.lower(): c for c in df.columns}
    y_true_col = cols.get("y_true") or cols.get("target") or cols.get("label") or cols.get("evento") or cols.get("inundacao")
    y_score_col = cols.get("y_score") or cols.get("score") or cols.get("proba") or cols.get("probabilidade") or cols.get("prediction") or cols.get("previsao")
    if not y_true_col or not y_score_col:
        raise ValueError(f"Colunas y_true/y_score nao encontradas. Disponiveis: {list(df.columns)}")
    print(f"[INFO] Usando y_true='{y_true_col}' e y_score='{y_score_col}'")
    return df[y_true_col].values, df[y_score_col].values

def main():
    print("=== CURVA PRECISION-RECALL — DADOS REAIS ===")
    y_true, y_score = carregar_predicoes()
    prec, rec, _ = precision_recall_curve(y_true, y_score)
    pr_auc = average_precision_score(y_true, y_score)
    print(f"\n[RESULTADO] PR-AUC = {pr_auc:.4f}")
    linhas = []
    for t in THRESHOLDS:
        y_pred = (y_score >= t).astype(int)
        p = precision_score(y_true, y_pred, zero_division=0)
        r = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        linhas.append({"threshold": t, "precision": round(p, 4), "recall": round(r, 4), "f1": round(f1, 4)})
    tabela = pd.DataFrame(linhas)
    print("\n[ TABELA POR THRESHOLD ]")
    print(tabela.to_string(index=False))
    tabela.to_csv(os.path.join(OUT_DIR, "curva_pr_tabela.csv"), index=False)
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(rec, prec, color="darkblue", lw=2, label=f"PR curve (AP={pr_auc:.4f})")
    ax.set_xlabel("Recall"); ax.set_ylabel("Precision")
    ax.set_title("Curva Precision-Recall — ARCTURUS (dados reais)")
    ax.legend(loc="lower left"); ax.grid(True, alpha=0.3)
    fig.savefig(os.path.join(OUT_DIR, "curva_pr_real.png"), dpi=150, bbox_inches="tight")
    plt.close(fig)
    resultado = {"fonte_dados": PRED_PATH, "pr_auc": round(float(pr_auc), 4),
                 "n_amostras": int(len(y_true)),
                 "tabela": tabela.to_dict(orient="records"),
                 "melhor_f1": tabela.loc[tabela["f1"].idxmax()].to_dict() if len(tabela) else None}
    with open(os.path.join(OUT_DIR, "curva_pr_completa.json"), "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"\n[OK] Artefatos salvos em {OUT_DIR}/")
    print("=== FIM ===")

if __name__ == "__main__":
    main()
