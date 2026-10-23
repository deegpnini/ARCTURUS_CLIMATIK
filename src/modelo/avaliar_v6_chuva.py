import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True)
raw = raw.loc[:, ~raw.columns.duplicated()].sort_index()
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

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
base = list(X.columns)

ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
media = ch.mean(axis=1)
for k in (1, 3, 6, 12, 24, 48):
    X[f"bacia_{k}h"] = media.rolling(k, min_periods=k).sum().reindex(g.index, method="ffill")
X["bacia_max3h"] = ch.rolling(3, min_periods=3).sum().max(axis=1).reindex(g.index, method="ffill")
X["bacia_pontos_chovendo"] = (ch.rolling(3, min_periods=3).sum() > 5).sum(axis=1).reindex(g.index, method="ffill")
com = list(X.columns)
print("features base:", len(base), "| com chuva da bacia:", len(com))

rmse = lambda a, b: float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))

def boot_diff(y, p1, p2, idx, n=500):
    rng = np.random.default_rng(0)
    dias = pd.Series(np.arange(len(y))).groupby(np.asarray(idx.date)).apply(list).tolist()
    out = []
    for _ in range(n):
        ii = np.concatenate([dias[k] for k in rng.integers(0, len(dias), len(dias))])
        out.append(rmse(y[ii], p1[ii]) - rmse(y[ii], p2[ii]))
    return np.percentile(out, [2.5, 97.5])

def treinar(cols, tr, va, seed):
    P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
             feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=seed, verbose=-1)
    dtr = lgb.Dataset(tr[cols], tr["y"])
    dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
    return lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])

for H, n in ((1, 4), (3, 12), (6, 24)):
    y = (c.shift(-n) - c).rename("y")
    D = X.join(y).dropna(subset=["y", "cota"])
    tr = D[D.index < "2025-01-01"]
    va = D[(D.index >= "2025-01-01") & (D.index < "2025-07-01")]
    te = D[D.index >= "2025-07-01"]
    yt, sub = te["y"].values, (te["delta_60m"] > 5).values
    print(f"\n=== {H}h | treino {len(tr)} val {len(va)} teste {len(te)} ===")
    print(f"zero            geral={rmse(yt, 0):.2f} subida={rmse(yt[sub], 0):.2f}")
    P = {}
    for nome, cols in (("so_ponto", base), ("com_bacia", com)):
        ps = [treinar(cols, tr, va, s).predict(te[cols]) if False else None for s in ()]
        ps = []
        for s in range(3):
            b = treinar(cols, tr, va, s)
            ps.append(b.predict(te[cols], num_iteration=b.best_iteration))
        P[nome] = np.mean(ps, axis=0)
        print(f"{nome:15s} geral={rmse(yt, P[nome]):.2f} subida={rmse(yt[sub], P[nome][sub]):.2f}")
    lo, hi = boot_diff(yt, P["so_ponto"], P["com_bacia"], te.index)
    print(f"RMSE(so_ponto) - RMSE(com_bacia): IC95% [{lo:.3f}, {hi:.3f}] cm (positivo = chuva da bacia ajuda)")
