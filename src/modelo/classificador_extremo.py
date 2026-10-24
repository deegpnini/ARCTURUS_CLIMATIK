import numpy as np
import pandas as pd
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True).sort_index()
raw = raw.loc[:, ~raw.columns.duplicated()]
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

# Features
X = pd.DataFrame(index=g.index)
X["cota"] = c
for m in (15, 30, 60, 180, 360, 720, 1440):
    X[f"cota_lag_{m}m"] = c.shift(m // 15)
X["delta_15m"], X["delta_60m"], X["delta_180m"] = c - c.shift(1), c - c.shift(4), c - c.shift(12)
X["aceleracao_1h"] = X["delta_60m"] - (c.shift(4) - c.shift(8))
r = c.rolling(48, min_periods=40)
X["cota_std_12h"], X["cota_max_12h"], X["cota_min_12h"] = r.std(), r.max(), r.min()
for col in g.columns:
    if col.startswith("chuva_"):
        X[col] = g[col]
h = g.index.hour + g.index.minute / 60
X["sin_hora"], X["cos_hora"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
d = g.index.dayofyear / 365.0
X["sin_dia_ano"], X["cos_dia_ano"] = np.sin(2 * np.pi * d), np.cos(2 * np.pi * d)

ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
for lag_h in [4, 6, 8]:
    X[f"bacia_lag_{lag_h}h"] = media.shift(lag_h * 4).reindex(g.index, method="ffill")
for k in (3, 6, 12):
    X[f"bacia_{k}h"] = media.rolling(k, min_periods=k).sum().reindex(g.index, method="ffill")

# Alvo binário: subida > 50 cm em 6h
y_6h = c.shift(-24) - c
y = (y_6h > 50).astype(int).rename("y")

D = X.join(y).dropna(subset=["y", "cota"])
tr = D[D.index < "2025-01-01"]
va = D[(D.index >= "2025-01-01") & (D.index < "2025-07-01")]
te = D[D.index >= "2025-07-01"]

print(f"Treino: {len(tr)} | Validação: {len(va)} | Teste: {len(te)}")
print(f"Eventos positivos no treino: {tr['y'].sum()} | no teste: {te['y'].sum()}")

# Treinar classificador
features = [c for c in D.columns if c != "y"]
P = dict(objective="binary", metric="auc", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=100, feature_fraction=0.8, bagging_fraction=0.8,
         bagging_freq=1, seed=42, verbose=-1)
dtr = lgb.Dataset(tr[features], tr["y"])
dva = lgb.Dataset(va[features], va["y"], reference=dtr)
b = lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])

# Avaliar
pred = b.predict(te[features], num_iteration=b.best_iteration)
auc_roc = roc_auc_score(te["y"], pred)
print(f"\nAUC-ROC: {auc_roc:.4f}")

# Curva de precisão-recall
precision, recall, thresholds = precision_recall_curve(te["y"], pred)
auc_pr = auc(recall, precision)
print(f"AUC-PR: {auc_pr:.4f}")

# Testar limiares
print(f"\n{'Limiar':>10} | {'Precisão':>10} | {'Recall':>10} | {'F1':>10}")
print("-" * 50)
for thresh in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]:
    pred_bin = (pred >= thresh).astype(int)
    tp = ((pred_bin == 1) & (te["y"] == 1)).sum()
    fp = ((pred_bin == 1) & (te["y"] == 0)).sum()
    fn = ((pred_bin == 0) & (te["y"] == 1)).sum()
    prec = tp / max(tp + fp, 1) * 100
    rec = tp / max(tp + fn, 1) * 100
    f1 = 2 * prec * rec / max(prec + rec, 1) if (prec + rec) > 0 else 0
    print(f"{thresh:>10.1f} | {prec:>9.1f}% | {rec:>9.1f}% | {f1:>9.1f}%")
