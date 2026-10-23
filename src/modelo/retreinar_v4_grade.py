import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True)
raw = raw.loc[:, ~raw.columns.duplicated()].sort_index()
raw = raw[~raw.index.duplicated(keep="last")]

# Diagnóstico do método antigo: quantos pares "4 linhas à frente" são 1h reais?
t = raw.index.to_series()
print(f"Linhas: {len(raw)} | pares de 4 linhas que são 1h reais: {((t.shift(-4) - t) == pd.Timedelta('1h')).mean():.1%}")

# Grade regular de 15 min: lacunas viram NaN, não são "puladas"
g = raw.resample("15min").last()
c = g["cota"]
print(f"Grade: {len(g)} passos | com cota: {c.notna().mean():.1%}")

X = pd.DataFrame(index=g.index)
X["cota"] = c
for m in (15, 30, 60, 180, 360, 720, 1440):
    X[f"cota_lag_{m}m"] = c.shift(m // 15)
X["delta_15m"] = c - c.shift(1)
X["delta_60m"] = c - c.shift(4)
X["delta_180m"] = c - c.shift(12)
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

# Montante: delta de 1h medido em t-2h (usa só dado de t-2h ou mais antigo)
for nome in ("sao_mauricio", "rio_fortuna"):
    a = g[f"{nome}_cota_abs"].ffill(limit=4)
    X[f"{nome}_delta_1h_lag2h"] = (a - a.shift(4)).shift(8)
com = list(X.columns)

# Alvo por tempo (na grade, 4 passos = 1h)
y = (c.shift(-4) - c).rename("y")
n_out = int((y.abs() >= 150).sum())
y = y.where(y.abs() < 150)
print(f"Alvos descartados por |delta| >= 150 cm: {n_out}")
D = X.join(y).dropna(subset=["y", "cota"])
tr = D[D.index < "2025-01-01"]
va = D[(D.index >= "2025-01-01") & (D.index < "2025-07-01")]
te = D[D.index >= "2025-07-01"]
print(f"Treino {len(tr)} | Validação {len(va)} | Teste {len(te)}")

P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
         feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
rmse = lambda a, b: float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))
sub = (te["delta_60m"] > 5).values
res = {"persistencia": {"geral": rmse(te["y"], 0), "subida": rmse(te["y"][sub], 0)}}

for nome, cols in (("sem_montante", base), ("com_montante", com)):
    dtr = lgb.Dataset(tr[cols], tr["y"])
    dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
    b = lgb.train(P, dtr, 3000, valid_sets=[dva],
                  callbacks=[lgb.early_stopping(100, verbose=False)])
    p = b.predict(te[cols], num_iteration=b.best_iteration)
    res[nome] = {"geral": rmse(te["y"], p), "subida": rmse(te["y"][sub], p[sub]),
                 "iteracoes": b.best_iteration, "n_features": len(cols)}
    b.save_model(str(BASE / "modelos" / f"modelo_delta_1h_v4_{nome}.txt"),
                 num_iteration=b.best_iteration)

print(f"\nTeste: {len(te)} linhas | subida: {int(sub.sum())} linhas")
for k, v in res.items():
    print(k, {a: (round(x, 2) if isinstance(x, float) else x) for a, x in v.items()})
json.dump({"teste": ">=2025-07-01", "validacao": "2025-01..06", "treino": "<2025-01-01",
           "resultados": res}, open(BASE / "modelos" / "manifesto_v4.json", "w"), indent=2)
