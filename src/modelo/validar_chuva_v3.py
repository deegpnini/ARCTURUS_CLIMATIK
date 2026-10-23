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

ch0 = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch0 = ch0.drop(columns=["braco_norte"], errors="ignore")
media = ch0.mean(axis=1)

def feats(ch):
    Z = pd.DataFrame(index=g.index)
    for lag_h in [4, 6, 8]:
        Z[f"bacia_lag_{lag_h}h"] = ch.mean(axis=1).shift(lag_h * 4).reindex(g.index, method="ffill")
    for k in (3, 6, 12):
        Z[f"bacia_{k}h"] = ch.mean(axis=1).rolling(k, min_periods=k).sum().reindex(g.index, method="ffill")
    return Z

def deslocar(dias):
    s = ch0.copy(); s.index = s.index + pd.Timedelta(days=dias); return s

variantes = {"real": ch0, "placebo_7d": deslocar(7), "placebo_45d": deslocar(45)}
rmse = lambda a, b: float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))

def treinar(cols, tr, va, seed):
    P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
             feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=seed, verbose=-1)
    dtr = lgb.Dataset(tr[cols], tr["y"])
    dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
    return lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])

def ic_semanal(y, p1, p2, idx, n=500):
    sem = np.asarray(idx.to_period("W").astype(str))
    grupos = pd.Series(np.arange(len(y))).groupby(sem).apply(list).tolist()
    rng = np.random.default_rng(0)
    out = []
    for _ in range(n):
        ii = np.concatenate([grupos[k] for k in rng.integers(0, len(grupos), len(grupos))])
        out.append(rmse(y[ii], p1[ii]) - rmse(y[ii], p2[ii]))
    return np.percentile(out, [2.5, 97.5])

for H, n in ((3, 12), (6, 24)):
    D0 = X.join((c.shift(-n) - c).rename("y"))
    def rodar(Z):
        D = (D0 if Z is None else D0.join(Z)).dropna(subset=["y", "cota"])
        cols = base + ([] if Z is None else list(Z.columns))
        tr, va = D[D.index < "2025-01-01"], D[(D.index >= "2025-01-01") & (D.index < "2025-07-01")]
        te = D[D.index >= "2025-07-01"]
        ps = []
        for s in range(3):
            b = treinar(cols, tr, va, s)
            ps.append(b.predict(te[cols], num_iteration=b.best_iteration))
        return te, np.mean(ps, axis=0)
    
    te, p0 = rodar(None)
    yt, sub = te["y"].values, (te["delta_60m"] > 5).values
    print(f"\n{H}h base      geral={rmse(yt, p0):.2f} subida={rmse(yt[sub], p0[sub]):.2f}")
    for nome, ch in variantes.items():
        _, p = rodar(feats(ch))
        lo, hi = ic_semanal(yt, p0, p, te.index)
        print(f"{H}h {nome:12s} geral={rmse(yt, p):.2f} subida={rmse(yt[sub], p[sub]):.2f} | ganho IC95% (blocos semanais) [{lo:.3f}, {hi:.3f}]")
