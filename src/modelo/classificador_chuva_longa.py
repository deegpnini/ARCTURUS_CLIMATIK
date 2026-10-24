import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from sklearn.metrics import roc_auc_score, average_precision_score

LIM = float(sys.argv[1]) if len(sys.argv) > 1 else 300.0
BASE = Path(__file__).resolve().parents[2]

s = pd.read_csv(BASE / "data" / "ana_longa84580000.csv")
s.columns = ["data", "cota"]
s["data"] = pd.to_datetime(s["data"], errors="coerce")
s["cota"] = pd.to_numeric(s["cota"], errors="coerce")
s = s.dropna(subset=["data"]).drop_duplicates("data").set_index("data").sort_index()
c = s["cota"].asfreq("D")   # calendário completo: lacunas viram NaN e o shift passa a ser por dia

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
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])   # só início de cheia

tr = D[D.index < "2000-01-01"]
va = D[(D.index >= "2000-01-01") & (D.index < "2010-01-01")]
te = D[D.index >= "2010-01-01"]
for nome, d in (("treino", tr), ("validação", va), ("teste", te)):
    print(f"{nome}: {len(d)} dias | inícios de cheia: {int(d['y'].sum())} ({d['y'].mean():.1%})")

P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)

def treinar(cols):
    dtr = lgb.Dataset(tr[cols], tr["y"])
    dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
    b = lgb.train(P, dtr, 2000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
    return (pd.Series(b.predict(va[cols], num_iteration=b.best_iteration), index=va.index),
            pd.Series(b.predict(te[cols], num_iteration=b.best_iteration), index=te.index))

scores = {"regra_chuva_2d": (va["chuva_2d"].fillna(0), te["chuva_2d"].fillna(0)),
          "so_cota": treinar(base), "cota+chuva": treinar(com)}

def agrupar(datas, gap=3):
    out, ult = [], None
    for t in datas:
        if ult is None or (t - ult).days > gap:
            out.append(t)
        ult = t
    return out

pos = te["y"] == 1
eventos = agrupar(te.index[pos.values])
anos = len(te) / 365.25   # aproximado: conta só dias elegíveis (cota abaixo do limiar e com dado)
npos_va = int((va["y"] == 1).sum())
print(f"\nprevalência no teste: {te['y'].mean():.3f} | eventos: {len(eventos)} | anos de observação (aprox.): {anos:.1f}")
if npos_va < 5:
    print(f"AVISO: só {npos_va} positivos na validação; limiar por quantil dos escores (menos confiável)")
for nome, (sv, st) in scores.items():
    auc, ap = roc_auc_score(te["y"], st), average_precision_score(te["y"], st)
    if npos_va >= 5:
        thr = np.quantile(sv[va["y"] == 1], 0.2)          # limiar da validação: recall 80%
    else:
        thr = np.quantile(sv, 1 - max(3 * va["y"].mean(), 0.01))
    al = st >= thr
    det = sum(al.loc[t0 - pd.Timedelta(days=1): t0].any() for t0 in eventos)
    ini = agrupar(te.index[al.values])
    falsos = sum(not pos.loc[t: t + pd.Timedelta(days=3)].any() for t in ini)
    print(f"{nome:15s} AUC={auc:.3f} AP={ap:.3f} | limiar={thr:.2f} | eventos {det}/{len(eventos)} | alarmes/ano {len(ini)/anos:.1f} | falsos/ano {falsos/anos:.1f}")
