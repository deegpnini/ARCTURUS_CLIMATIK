import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import average_precision_score, recall_score, precision_score, f1_score
from pathlib import Path
import json

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a série da ANA
s = pd.read_csv(BASE / "data" / "ana_longa84580000.csv")
s.columns = ["data", "cota"]
s["data"] = pd.to_datetime(s["data"], errors="coerce")
s["cota"] = pd.to_numeric(s["cota"], errors="coerce")
s = s.dropna(subset=["data"]).drop_duplicates("data").set_index("data").sort_index()
c = s["cota"].asfreq("D")

# 2. Carregar a chuva longa (5 pontos) e a chuva a montante histórica
ch = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
                for f in sorted((BASE / "data").glob("chuva_longa_*.csv"))], axis=1).reindex(c.index)
bacia = ch.mean(axis=1)

# Carregar a chuva a montante histórica (1940-2026)
chuva_montante = pd.read_csv(BASE / "data" / "chuva_montante_historica.csv", index_col=0, parse_dates=True)
chuva_montante = chuva_montante.reindex(c.index).fillna(0)

# 3. Criar features
X = pd.DataFrame(index=c.index)
X["cota"] = c
X["d1"], X["d3"] = c - c.shift(1), c - c.shift(3)
X["max3"] = c.rolling(3, min_periods=3).max()
X["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
X["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
for k in (1, 2, 3, 5, 10, 30):
    X[f"chuva_{k}d"] = bacia.rolling(k, min_periods=k).sum()
X["chuva_max_ponto_2d"] = ch.rolling(2, min_periods=2).sum().max(axis=1)
X["chuva_montante_24h"] = chuva_montante["chuva_montante_24h"] if "chuva_montante_24h" in chuva_montante.columns else 0
X["chuva_montante_72h"] = chuva_montante["chuva_montante_72h"] if "chuva_montante_72h" in chuva_montante.columns else 0
X["chuva_montante_7d"] = chuva_montante["chuva_montante_7d"] if "chuva_montante_7d" in chuva_montante.columns else 0

# 4. Alvo: cheia em 2 dias (média diária >= 300)
LIM = 300
fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna())
D = X.join(y.rename("y"))
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])

# 5. Identificar os eventos (>= 300 cm, com declustering)
eventos = D[D["y"] == 1].index
eventos_agrupados = []
ultimo = None
for ev in eventos:
    if ultimo is None or (ev - ultimo).days > 3:
        eventos_agrupados.append(ev)
    ultimo = ev

eventos_agrupados = eventos_agrupados[:31]
print(f"Total de eventos: {len(eventos_agrupados)}")

# 6. LOEO com a chuva a montante histórica
W = pd.Timedelta(days=7)
BUFFER = pd.Timedelta(days=1)
features = [col for col in D.columns if col != "y"]
P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)

oof = []
for i, ev in enumerate(eventos_agrupados):
    mask_teste = (D.index >= ev - W) & (D.index <= ev + W)
    D_teste = D[mask_teste]
    mask_treino = (D.index < ev - W - BUFFER) | (D.index > ev + W + BUFFER)
    D_treino = D[mask_treino]
    if len(D_treino) < 100 or len(D_teste) < 5:
        continue
    dtr = lgb.Dataset(D_treino[features], D_treino["y"])
    b = lgb.train(P, dtr, 500)
    y_score = b.predict(D_teste[features])
    y_true = D_teste["y"].values
    oof.append(pd.DataFrame({"evento": ev, "y": y_true, "p": y_score}))
    print(f"Evento {i+1}/{len(eventos_agrupados)}: positivos={y_true.sum()}, prob_range=[{y_score.min():.4f}, {y_score.max():.4f}]")

# 7. Concatenar as predições out-of-fold
oof = pd.concat(oof, ignore_index=True)
print(f"\nTotal de predições out-of-fold: {len(oof)}")

# 8. Métricas agregadas
if oof["y"].nunique() > 1:
    pr_auc = average_precision_score(oof["y"], oof["p"])
else:
    pr_auc = 0.0

limiar = 0.05
y_pred = (oof["p"] > limiar).astype(int)
recall = recall_score(oof["y"], y_pred, zero_division=0)
precision = precision_score(oof["y"], y_pred, zero_division=0)
f1 = f1_score(oof["y"], y_pred, zero_division=0)

print(f"\n=== RESULTADO DO LOEO (COM CHUVA A MONTANTE HISTÓRICA) ===")
print(f"PR-AUC: {pr_auc:.4f}")
print(f"Recall: {recall:.4f}")
print(f"Precision: {precision:.4f}")
print(f"F1: {f1:.4f}")

# 9. Salvar o relatório
relatorio = {
    "total_eventos": len(eventos_agrupados),
    "total_predicoes": len(oof),
    "pr_auc": float(pr_auc),
    "recall": float(recall),
    "precision": float(precision),
    "f1": float(f1),
    "limiar": limiar,
    "chuva_montante": "historica",
}
with open(BASE / "docs" / "RELATORIO_LOEO_MONTANTE_HISTORICO.json", "w") as f:
    json.dump(relatorio, f, indent=2, default=str)
print(f"\n✅ Relatório salvo em: docs/RELATORIO_LOEO_MONTANTE_HISTORICO.json")
