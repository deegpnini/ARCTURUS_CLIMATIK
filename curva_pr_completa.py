#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Curva Precision-Recall para o modelo de sombra (limiares 0.05 a 0.50)."""

import psycopg2
from sklearn.metrics import precision_recall_curve, auc
import matplotlib.pyplot as plt

DB_URL = "postgresql:///arcturus"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

# Busca as predições com y_true e y_score
cur.execute("""
    SELECT y_score, y_true
    FROM predicoes_shadow
    WHERE y_true IS NOT NULL
      AND y_score IS NOT NULL
      AND valido IS TRUE
      AND stale IS FALSE
""")
rows = cur.fetchall()
cur.close()
conn.close()

if not rows:
    print("[ERRO] Sem dados suficientes para a curva PR.")
    exit(1)

# Converte para binário: y_true > 0 (subida) = 1, senão = 0
y_scores = [r[0] for r in rows]
y_true_bin = [1 if r[1] > 0 else 0 for r in rows]

# Calcula a curva PR
precision, recall, thresholds = precision_recall_curve(y_true_bin, y_scores)
pr_auc = auc(recall, precision)

print(f"Amostras: {len(rows)}")
print(f"PR-AUC: {pr_auc:.4f}")

# Mostra os limiares
print("\n=== Limiares ===")
for t in [0.05, 0.10, 0.15, 0.20, 0.25, 0.30, 0.40, 0.50]:
    idx = (thresholds >= t).argmax() if any(thresholds >= t) else -1
    if idx >= 0 and idx < len(thresholds):
        print(f"  T={t:.2f}: Precision={precision[idx]:.2f}, Recall={recall[idx]:.2f}")

# Plota a curva
plt.figure(figsize=(8, 6))
plt.plot(recall, precision, label=f"PR-AUC = {pr_auc:.4f}")
plt.xlabel("Recall")
plt.ylabel("Precision")
plt.title("Curva Precision-Recall (ARCTURUS)")
plt.legend()
plt.grid(True)
plt.savefig("resultados/curva_pr.png")
print("\n[OK] Gráfico salvo em resultados/curva_pr.png")
