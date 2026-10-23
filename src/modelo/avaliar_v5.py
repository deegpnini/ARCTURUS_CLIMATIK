import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from sklearn.linear_model import LinearRegression

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
for nome in ("sao_mauricio", "rio_fortuna"):
    a = g[f"{nome}_cota_abs"].ffill(limit=4)
    X[f"{nome}_delta_1h_lag2h"] = (a - a.shift(4)).shift(8)
com = list(X.columns)

def treinar(cols, tr, va, seed):
    P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
             feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=seed, verbose=-1)
    dtr = lgb.Dataset(tr[cols], tr["y"])
    dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
    return lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])

rmse = lambda a, b: float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))

def boot_diff(y, p1, p2, idx, n=500):
    rng = np.random.default_rng(0)
    dias = pd.Series(np.arange(len(y))).groupby(np.asarray(idx.date)).apply(list).tolist()
    out = []
    for _ in range(n):
        ii = np.concatenate([dias[k] for k in rng.integers(0, len(dias), len(dias))])
        out.append(rmse(y[ii], p1[ii]) - rmse(y[ii], p2[ii]))
    return np.percentile(out, [2.5, 97.5])

resumo = {}
for H, n in ((1, 4), (3, 12), (6, 24)):
    lim = 150 * H
    y = c.shift(-n) - c
    n_out = int((y.abs() >= lim).sum())
    y = y.where(y.abs() < lim).rename("y")
    D = X.join(y).dropna(subset=["y", "cota"])
    tr = D[D.index < "2025-01-01"]
    va = D[(D.index >= "2025-01-01") & (D.index < "2025-07-01")]
    te = D[D.index >= "2025-07-01"]
    yt = te["y"].values
    sub = (te["delta_60m"] > 5).values
    print(f"\n=== Horizonte {H}h | descartados |y|>={lim}: {n_out} | treino {len(tr)} val {len(va)} teste {len(te)} (subida: {int(sub.sum())}) ===")

    dc = ["delta_15m", "delta_60m", "delta_180m"]
    lin = LinearRegression().fit(tr[dc].fillna(0), tr["y"])
    preds = {"zero": np.zeros(len(te)), "linear_deltas": lin.predict(te[dc].fillna(0))}
    seeds = {}
    for nome, cols in (("sem_montante", base), ("com_montante", com)):
        ps, rs, rsub = [], [], []
        for s in range(5):
            b = treinar(cols, tr, va, s)
            p = b.predict(te[cols], num_iteration=b.best_iteration)
            ps.append(p); rs.append(rmse(yt, p)); rsub.append(rmse(yt[sub], p[sub]))
        preds[nome] = np.mean(ps, axis=0)
        seeds[nome] = (np.mean(rs), np.std(rs), np.mean(rsub), np.std(rsub))
        b.save_model(str(BASE / "modelos" / f"modelo_delta_{H}h_v5_{nome}.txt"), num_iteration=b.best_iteration)

    res = {}
    for k in ("zero", "linear_deltas"):
        res[k] = {"geral": rmse(yt, preds[k]), "subida": rmse(yt[sub], preds[k][sub])}
        print(f"{k:14s} geral={res[k]['geral']:.2f} subida={res[k]['subida']:.2f}")
    for k, (m, sd, ms, sds) in seeds.items():
        res[k] = {"geral": m, "geral_sd": sd, "subida": ms, "subida_sd": sds}
        print(f"{k:14s} geral={m:.2f}±{sd:.2f} subida={ms:.2f}±{sds:.2f}  (5 sementes)")
    lo, hi = boot_diff(yt, preds["sem_montante"], preds["com_montante"], te.index)
    print(f"RMSE(sem) - RMSE(com): IC95% [{lo:.3f}, {hi:.3f}] cm  (se inclui 0, montante sem evidência de ganho)")

    picos = []
    for ts in te["cota"].sort_values(ascending=False).index:
        if all(abs((ts - p).total_seconds()) > 3 * 86400 for p in picos):
            picos.append(ts)
        if len(picos) == 5:
            break
    for ts in picos:
        w = (te.index >= ts - pd.Timedelta("24h")) & (te.index <= ts)
        for nome in ("zero", "sem_montante"):
            e = preds[nome][w] - yt[w]
            print(f"  pico {ts:%Y-%m-%d %H:%M} cota={te.loc[ts, 'cota']:.0f} | {nome:13s} RMSE={np.sqrt((e**2).mean()):.1f} pior_subestimacao={e.min():.1f}")
    resumo[f"{H}h"] = res

json.dump(resumo, open(BASE / "modelos" / "manifesto_v5.json", "w"), indent=2)
