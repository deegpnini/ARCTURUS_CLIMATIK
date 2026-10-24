import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from scipy.stats import beta
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

LIM = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
BASE = Path(__file__).resolve().parents[2]

s = pd.read_csv(BASE / "data" / "ana_longa84580000.csv")
s.columns = ["data", "cota"]
s["data"] = pd.to_datetime(s["data"], errors="coerce")
s["cota"] = pd.to_numeric(s["cota"], errors="coerce")
s = s.dropna(subset=["data"]).drop_duplicates("data").set_index("data").sort_index()
c = s["cota"].asfreq("D")
ch = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
                for f in sorted((BASE / "data").glob("chuva_longa_*.csv"))], axis=1).reindex(c.index)
bacia = ch.mean(axis=1)

X = pd.DataFrame(index=c.index)
X["cota"] = c
X["d1"], X["d3"] = c - c.shift(1), c - c.shift(3)
X["max3"] = c.rolling(3, min_periods=3).max()
X["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
X["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
base = list(X.columns)
for k in (1, 2, 3, 5, 10, 30):
    X[f"chuva_{k}d"] = bacia.rolling(k, min_periods=k).sum()
X["chuva_max_ponto_2d"] = ch.rolling(2, min_periods=2).sum().max(axis=1)
com = base + [col for col in X.columns if col.startswith("chuva_")]

fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna())
D = X.join(y.rename("y"))
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])
tr = D[D.index < "2000-01-01"]
va = D[(D.index >= "2000-01-01") & (D.index < "2010-01-01")]
te = D[D.index >= "2010-01-01"]
anos_va, anos_te = len(va) / 365.25, len(te) / 365.25

P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, verbose=-1)

def agrupar(datas, gap=3):
    out, ult = [], None
    for t in datas:
        if ult is None or (t - ult).days > gap:
            out.append(t)
        ult = t
    return out

def cp(k, n):
    lo = beta.ppf(0.025, k, n - k + 1) if k > 0 else 0.0
    hi = beta.ppf(0.975, k + 1, n - k) if k < n else 1.0
    return lo, hi

def lgbm(cols, seeds=3):
    sv, st = np.zeros(len(va)), np.zeros(len(te))
    for sd in range(seeds):
        dtr = lgb.Dataset(tr[cols], tr["y"])
        dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
        b = lgb.train(dict(P, seed=sd), dtr, 2000, valid_sets=[dva],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
        sv += b.predict(va[cols], num_iteration=b.best_iteration) / seeds
        st += b.predict(te[cols], num_iteration=b.best_iteration) / seeds
    return pd.Series(sv, index=va.index), pd.Series(st, index=te.index)

def logit(cols):
    m = make_pipeline(StandardScaler(), LogisticRegression(max_iter=2000))
    m.fit(tr[cols].fillna(0), tr["y"])
    return (pd.Series(m.predict_proba(va[cols].fillna(0))[:, 1], index=va.index),
            pd.Series(m.predict_proba(te[cols].fillna(0))[:, 1], index=te.index))

modelos = {"regra_chuva_2d": (va["chuva_2d"].fillna(0), te["chuva_2d"].fillna(0)),
           "logistica": logit(com), "lgbm_so_cota": lgbm(base), "lgbm_cota+chuva": lgbm(com)}

pos = te["y"] == 1
eventos = agrupar(te.index[pos.values])

def cruzamento(t0):
    for k in (1, 2):
        t = t0 + pd.Timedelta(days=k)
        if c.get(t, np.nan) >= LIM:
            return t
    return None

def limiar_por_orcamento(sv, B):
    for q in np.linspace(0.90, 0.9999, 400):
        thr = np.quantile(sv, q)
        if len(agrupar(sv.index[(sv >= thr).values])) / anos_va <= B:
            return thr
    return float(sv.max())

print(f"limiar de cheia: {LIM:.0f} cm (média diária) | eventos no teste: {len(eventos)} | anos de observação (aprox.): {anos_te:.1f}")
for nome, (sv, st) in modelos.items():
    for B in (2, 5, 10, 20):
        thr = limiar_por_orcamento(sv, B)
        al = st >= thr
        ini = agrupar(te.index[al.values])
        falsos = sum(not pos.loc[t: t + pd.Timedelta(days=3)].any() for t in ini)
        det, leads = 0, []
        for t0 in eventos:
            cr = cruzamento(t0)
            if cr is None:
                continue
            dias = pd.date_range(cr - pd.Timedelta(days=3), cr - pd.Timedelta(days=1))
            hit = al.reindex(dias, fill_value=False)
            if hit.any():
                det += 1
                leads.append((cr - hit.index[hit.values][0]).days)
        lo, hi = cp(det, len(eventos))
        lead = f"{np.mean(leads):.1f}" if leads else "-"
        print(f"{nome:16s} orçamento={B:>2}/ano limiar={thr:.3f} | detectados {det}/{len(eventos)} "
              f"(IC95% {lo:.0%}-{hi:.0%}) | alarmes/ano {len(ini)/anos_te:5.1f} | falsos/ano {falsos/anos_te:5.1f} "
              f"| antecedência média {lead} d")
