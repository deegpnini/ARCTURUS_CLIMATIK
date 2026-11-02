#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A.C. Atlas / ARCTURUS — Curva Precision-Recall completa (threshold 0.05 a 0.50)
Gera tabela + gráfico + JSON.
"""
import os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")  # salvar sem abrir janela
import matplotlib.pyplot as plt
from sklearn.metrics import (
    precision_recall_curve, average_precision_score,
    precision_score, recall_score, f1_score
)

# --- CONFIG ---
OUT_DIR = "resultados"
os.makedirs(OUT_DIR, exist_ok=True)

# Caminho do arquivo de predições em modo sombra
# Ajuste conforme o dossiê: CSV ou JSON com colunas y_true e y_score
PRED_PATH = "dados/predicoes_shadow.csv"   # <- ajuste se necessário

# Thresholds a testar
THRESHOLDS = [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]

def carregar_predicoes():
    """Tenta carregar y_true e y_score de CSV. Se falhar, gera dados sintéticos
    apenas para validar o pipeline (NÃO usar em produção)."""
    if os.path.exists(PRED_PATH):
        df = pd.read_csv(PRED_PATH)
        print(f"[OK] Predições carregadas: {len(df)} linhas de {PRED_PATH}")
        # Procura colunas comuns
        cols = {c.lower(): c for c in df.columns}
        y_true_col = cols.get("y_true") or cols.get("target") or cols.get("label")
        y_score_col = cols.get("y_score") or cols.get("score") or cols.get("proba") or cols.get("prediction")
        if not y_true_col or not y_score_col:
            raise ValueError(f"Colunas y_true/y_score não encontradas. Colunas: {list(df.columns)}")
        return df[y_true_col].values, df[y_score_col].values, "real"
    else:
        print(f"[AVISO] {PRED_PATH} não encontrado.")
        print("[AVISO] Gerando dados SINTÉTICOS apenas para validar o pipeline.")
        print("[AVISO] Substitua por predições reais do modo sombra.")
        rng = np.random.default_rng(42)
        n = 500
        y_true = rng.integers(0, 2, n)
        y_score = np.clip(0.3 * y_true + rng.normal(0.35, 0.2, n), 0, 1)
        return y_true, y_score, "sintetico"

def calcular_tabela(y_true, y_score):
    linhas = []
    for t in THRESHOLDS:
        y_pred = (y_score >= t).astype(int)
        p = precision_score(y_true, y_pred, zero_division=0)
        r = recall_score(y_true, y_pred, zero_division=0)
        f1 = f1_score(y_true, y_pred, zero_division=0)
        linhas.append({"threshold": t, "precision": round(p, 4),
                       "recall": round(r, 4), "f1": round(f1, 4)})
    return pd.DataFrame(linhas)

def main():
    print("=== CURVA PRECISION-RECALL — ARCTURUS ===")
    y_true, y_score, fonte = carregar_predicoes()

    # Curva PR completa
    prec, rec, _ = precision_recall_curve(y_true, y_score)
    pr_auc = average_precision_score(y_true, y_score)
    print(f"[INFO] PR-AUC = {pr_auc:.4f} | Fonte = {fonte}")

    # Tabela por threshold
    tabela = calcular_tabela(y_true, y_score)
    print("\n[ TABELA POR THRESHOLD ]")
    print(tabela.to_string(index=False))

    # Salvar CSV da tabela
    csv_path = os.path.join(OUT_DIR, "curva_pr_tabela.csv")
    tabela.to_csv(csv_path, index=False)
    print(f"\n[OK] Tabela salva: {csv_path}")

    # Gráfico PR
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.plot(rec, prec, color="darkblue", lw=2, label=f"PR curve (AP={pr_auc:.4f})")
    ax.set_xlabel("Recall")
    ax.set_ylabel("Precision")
    ax.set_title("Curva Precision-Recall — ARCTURUS (LOEO)")
    ax.legend(loc="lower left")
    ax.grid(True, alpha=0.3)
    png_path = os.path.join(OUT_DIR, "curva_pr.png")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"[OK] Gráfico salvo: {png_path}")

    # JSON final
    resultado = {
        "fonte_dados": fonte,
        "pr_auc": round(float(pr_auc), 4),
        "tabela": tabela.to_dict(orient="records"),
        "melhor_f1": tabela.loc[tabela["f1"].idxmax()].to_dict() if len(tabela) else None,
    }
    json_path = os.path.join(OUT_DIR, "curva_pr_completa.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(resultado, f, ensure_ascii=False, indent=2)
    print(f"[OK] JSON salvo: {json_path}")
    print("\n=== FIM ===")

if __name__ == "__main__":
    main()
