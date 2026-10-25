import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from datetime import date
from pathlib import Path

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

X = pd.DataFrame(index=c.index)
X["cota"] = c
X["d1"], X["d3"] = c - c.shift(1), c - c.shift(3)
X["max3"] = c.rolling(3, min_periods=3).max()
X["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
X["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
for k in (1, 2, 3, 5, 10, 30):
    X[f"chuva_{k}d"] = bacia.rolling(k, min_periods=k).sum()
X["chuva_max_ponto_2d"] = ch.rolling(2, min_periods=2).sum().max(axis=1)
cols = list(X.columns)

fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna())
D = X.join(y.rename("y"))
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])
tr = D[D.index < "2000-01-01"]
va = D[(D.index >= "2000-01-01") & (D.index < "2010-01-01")]
te = D[D.index >= "2010-01-01"]
anos_va, anos_te = len(va) / 365.25, len(te) / 365.25

const = [k for k in cols if D[k].nunique() <= 1]
print("colunas constantes:", const)
assert not const, "há coluna constante; corrigir antes de treinar"

P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, verbose=-1)
sv, st, its = np.zeros(len(va)), np.zeros(len(te)), []
for sd in range(3):
    dtr = lgb.Dataset(tr[cols], tr["y"])
    dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
    b = lgb.train(dict(P, seed=sd), dtr, 2000, valid_sets=[dva],
                  callbacks=[lgb.early_stopping(100, verbose=False)])
    b.save_model(str(BASE / "modelos" / f"classificador_v2_seed{sd}.txt"), num_iteration=b.best_iteration)
    its.append(int(b.best_iteration))
    sv += b.predict(va[cols], num_iteration=b.best_iteration) / 3
    st += b.predict(te[cols], num_iteration=b.best_iteration) / 3
sv, st = pd.Series(sv, index=va.index), pd.Series(st, index=te.index)

def agrupar(datas, gap=3):
    out, ult = [], None
    for t in datas:
        if ult is None or (t - ult).days > gap:
            out.append(t)
        ult = t
    return out

def limiar_por_orcamento(B):
    for q in np.linspace(0.90, 0.9999, 400):
        thr = np.quantile(sv, q)
        if len(agrupar(sv.index[(sv >= thr).values])) / anos_va <= B:
            return float(thr)
    return float(sv.max())

def cruzamento(t0):
    for k in (1, 2):
        t = t0 + pd.Timedelta(days=k)
        if c.get(t, np.nan) >= LIM:
            return t
    return None

pos = te["y"] == 1
eventos = agrupar(te.index[pos.values])
thr_all = {}
print(f"iterações: {its} | eventos no teste: {len(eventos)} | anos (aprox.): {anos_te:.1f}")
for B in (2, 5, 10, 20):
    thr = limiar_por_orcamento(B)
    thr_all[str(B)] = thr
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
    print(f"orçamento {B:>2}/ano limiar={thr:.3f} | detectados {det}/{len(eventos)} | alarmes/ano {len(ini)/anos_te:.1f} | falsos/ano {falsos/anos_te:.1f}")

json.dump({"features": cols, "limiar_cheia_cm_media_diaria": LIM, "limiares_por_orcamento_ano": thr_all,
           "iteracoes": its, "treino": "<2000", "validacao": "2000-2009", "teste": ">=2010",
           "modelos": [f"classificador_v2_seed{i}.txt" for i in range(3)],
           "uso": "média das 3 sementes; limiar vale só para esta média", "gerado_em": str(date.today())},
          open(BASE / "modelos" / "manifesto_classificador_v2.json", "w"), indent=2, ensure_ascii=False)
print("manifesto salvo")
