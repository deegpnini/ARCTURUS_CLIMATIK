import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import roc_auc_score, precision_recall_curve, auc
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a série longa
caminho = BASE / "data" / "ana_longa84580000.csv"
df = pd.read_csv(caminho)
df.columns = ["data", "cota"]
df["data"] = pd.to_datetime(df["data"], errors="coerce")
df = df.dropna(subset=["data", "cota"])
df["cota"] = pd.to_numeric(df["cota"], errors="coerce")
df = df.dropna(subset=["cota"])
df = df.set_index("data").sort_index()

print(f"Período: {df.index.min()} a {df.index.max()}")
print(f"Total de dias: {len(df)}")

# 2. Criar as features (lags e deltas)
X = pd.DataFrame(index=df.index)
X["cota"] = df["cota"]
for lag in (1, 3, 7, 14, 30):
    X[f"cota_lag_{lag}d"] = df["cota"].shift(lag)
X["delta_3d"] = df["cota"] - df["cota"].shift(3)
X["delta_7d"] = df["cota"] - df["cota"].shift(7)
X["delta_14d"] = df["cota"] - df["cota"].shift(14)
r = df["cota"].rolling(30, min_periods=20)
X["cota_std_30d"] = r.std()
X["cota_max_30d"] = r.max()
X["cota_min_30d"] = r.min()
h = df.index.dayofyear / 365.0
X["sin_dia_ano"] = np.sin(2 * np.pi * h)
X["cos_dia_ano"] = np.cos(2 * np.pi * h)

# 3. Criar o alvo: subida > 100 cm em 7 dias
y = (df["cota"].shift(-7) - df["cota"] > 100).astype(int)

# 4. Juntar e limpar
D = X.join(y.rename("y")).dropna()
print(f"Amostras com features: {len(D)}")
print(f"Eventos positivos (subida > 100cm em 7d): {D['y'].sum()} ({D['y'].mean()*100:.1f}%)")

# 5. Split cronológico
tr = D[D.index < "2000-01-01"]
va = D[(D.index >= "2000-01-01") & (D.index < "2010-01-01")]
te = D[D.index >= "2010-01-01"]

print(f"\nTreino: {len(tr)} | Validação: {len(va)} | Teste: {len(te)}")
print(f"Positivos no treino: {tr['y'].sum()} | no teste: {te['y'].sum()}")

# 6. Treinar o classificador
features = [c for c in D.columns if c != "y"]
P = dict(objective="binary", metric="auc", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8,
         bagging_freq=1, seed=42, verbose=-1)
dtr = lgb.Dataset(tr[features], tr["y"])
dva = lgb.Dataset(va[features], va["y"], reference=dtr)
b = lgb.train(P, dtr, 1000, valid_sets=[dva], callbacks=[lgb.early_stopping(50, verbose=False)])

# 7. Avaliar
pred = b.predict(te[features], num_iteration=b.best_iteration)
auc_roc = roc_auc_score(te["y"], pred)
print(f"\nAUC-ROC: {auc_roc:.4f}")

precision, recall, thresholds = precision_recall_curve(te["y"], pred)
auc_pr = auc(recall, precision)
print(f"AUC-PR: {auc_pr:.4f}")

print(f"\n{'Limiar':>10} | {'Precisão':>10} | {'Recall':>10} | {'F1':>10}")
print("-" * 50)
for thresh in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]:
    pred_bin = (pred >= thresh).astype(int)
    tp = ((pred_bin == 1) & (te["y"] == 1)).sum()
    fp = ((pred_bin == 1) & (te["y"] == 0)).sum()
    fn = ((pred_bin == 0) & (te["y"] == 1)).sum()
    prec = tp / max(tp + fp, 1) * 100
    rec = tp / max(tp + fn, 1) * 100
    f1 = 2 * prec * rec / max(prec + rec, 1) if (prec + rec) > 0 else 0
    print(f"{thresh:>10.1f} | {prec:>9.1f}% | {rec:>9.1f}% | {f1:>9.1f}%")
