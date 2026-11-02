import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from scipy.stats import beta

LIM = 300.0
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

past = pd.DataFrame(index=c.index)
past["cota"] = c
past["d1"], past["d3"] = c - c.shift(1), c - c.shift(3)
past["max3"] = c.rolling(3, min_periods=3).max()
past["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
past["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
for k in (1, 2, 3, 5, 10, 30):
    past[f"chuva_{k}d"] = bacia.rolling(k, min_periods=k).sum()
past["chuva_max_ponto_2d"] = ch.rolling(2, min_periods=2).sum().max(axis=1)
base_cols = list(past.columns)

fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna()).rename("y")

def com_previsao(sigma, seed=0):
    rng = np.random.default_rng(seed)
    f1, f2 = bacia.shift(-1), bacia.shift(-2)
    if sigma > 0:
        f1 = f1 * np.exp(rng.normal(0, sigma, len(f1)))
        f2 = f2 * np.exp(rng.normal(0, sigma, len(f2)))
    return past.join(pd.DataFrame({"prev_1d": f1, "prev_2d": f1 + f2}, index=c.index))

def preparar(X):
    D = X.join(y)
    D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])
    return (D[D.index < "2000-01-01"],
            D[(D.index >= "2000-01-01") & (D.index < "2010-01-01")],
            D[D.index >= "2010-01-01"])

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

def cruzamento(t0):
    for k in (1, 2):
        t = t0 + pd.Timedelta(days=k)
        if c.get(t, np.nan) >= LIM:
            return t
    return None

def limiar(sv, B, anos):
    for q in np.linspace(0.90, 0.9999, 400):
        thr = np.quantile(sv, q)
        if len(agrupar(sv.index[(sv >= thr).values])) / anos <= B:
            return float(thr)
    return float(sv.max())

P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, verbose=-1)

def treinar(cols, tr, va, te, seeds=2):
    sv, st = np.zeros(len(va)), np.zeros(len(te))
    for sd in range(seeds):
        dtr = lgb.Dataset(tr[cols], tr["y"])
        dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
        b = lgb.train(dict(P, seed=sd), dtr, 2000, valid_sets=[dva],
                      callbacks=[lgb.early_stopping(100, verbose=False)])
        sv += b.predict(va[cols], num_iteration=b.best_iteration) / seeds
        st += b.predict(te[cols], num_iteration=b.best_iteration) / seeds
    return pd.Series(sv, index=va.index), pd.Series(st, index=te.index)

def avaliar(nome, sv, st, va, te):
    anos_va, anos_te = len(va) / 365.25, len(te) / 365.25
    pos = te["y"] == 1
    eventos = agrupar(te.index[pos.values])
    for B in (5, 10, 20):
        thr = limiar(sv, B, anos_va)
        al = st >= thr
        ini = agrupar(te.index[al.values])
        falsos = sum(not pos.loc[t: t + pd.Timedelta(days=3)].any() for t in ini)
        det = 0
        for t0 in eventos:
            cr = cruzamento(t0)
            if cr is None:
                continue
            dias = pd.date_range(cr - pd.Timedelta(days=3), cr - pd.Timedelta(days=1))
            det += int(al.reindex(dias, fill_value=False).any())
        lo, hi = cp(det, len(eventos))
        print(f"{nome:40s} orç={B:>2}/ano | detectados {det}/{len(eventos)} (IC95% {lo:.0%}-{hi:.0%}) "
              f"| alarmes/ano {len(ini)/anos_te:5.1f} | falsos/ano {falsos/anos_te:5.1f}")

for nome, sigma in (("A) sem chuva futura (= v2)", None),
                    ("B) previsao perfeita (limite superior)", 0.0),
                    ("C) previsao com erro (sigma=0.5)", 0.5)):
    X = past if sigma is None else com_previsao(sigma)
    cols = list(X.columns)
    tr, va, te = preparar(X)
    sv, st = treinar(cols, tr, va, te)
    avaliar(nome, sv, st, va, te)
    if sigma is not None:
        avaliar("   regra: soma prevista em 2 dias", va["prev_2d"].fillna(0), te["prev_2d"].fillna(0), va, te)
