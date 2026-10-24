import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True).sort_index()
raw = raw.loc[:, ~raw.columns.duplicated()]
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

# Features base (v8)
X = pd.DataFrame(index=g.index)
X["cota"] = c
for m in (15, 30, 60, 180, 360, 720, 1440):
    X[f"cota_lag_{m}m"] = c.shift(m // 15)
X["delta_15m"] = c - c.shift(1)
X["delta_60m"] = c - c.shift(4)
X["delta_180m"] = c - c.shift(12)
X["aceleracao_1h"] = X["delta_60m"] - (c.shift(4) - c.shift(8))
r = c.rolling(48, min_periods=40)
X["cota_std_12h"] = r.std()
X["cota_max_12h"] = r.max()
X["cota_min_12h"] = r.min()

# Chuva da bacia
ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
for lag_h in [4, 6, 8]:
    X[f"bacia_lag_{lag_h}h"] = media.shift(lag_h * 4).reindex(g.index, method="ffill")
for k in (3, 6, 12):
    X[f"bacia_{k}h"] = media.rolling(k, min_periods=k).sum().reindex(g.index, method="ffill")

h = g.index.hour + g.index.minute / 60
X["sin_hora"] = np.sin(2 * np.pi * h / 24)
X["cos_hora"] = np.cos(2 * np.pi * h / 24)
d = g.index.dayofyear / 365.0
X["sin_dia_ano"] = np.sin(2 * np.pi * d)
X["cos_dia_ano"] = np.cos(2 * np.pi * d)
base = list(X.columns)

# GloFAS (vazão simulada)
glofas = pd.read_csv(BASE / "data" / "flood_glofas_historico.csv", index_col=0, parse_dates=True).sort_index()
# Reamostrar para 15min e preencher (ffill)
glofas_15 = glofas.resample("15min").ffill().reindex(g.index, method="ffill")
X["glofas_vazao"] = glofas_15["vazao_glofas_m3s"].ffill()
X["glofas_lag_6h"] = X["glofas_vazao"].shift(24)
X["glofas_lag_12h"] = X["glofas_vazao"].shift(48)
com = list(X.columns)

print(f"Features base: {len(base)} | Com GloFAS: {len(com)}")

rmse = lambda a, b: float(np.sqrt(np.mean((np.asarray(a) - np.asarray(b)) ** 2)))

for H, n in ((3, 12), (6, 24)):
    y = (c.shift(-n) - c).rename("y")
    D = X.join(y).dropna(subset=["y", "cota"])
    tr = D[D.index < "2025-01-01"]
    va = D[(D.index >= "2025-01-01") & (D.index < "2025-07-01")]
    te = D[D.index >= "2025-07-01"]
    yt, sub = te["y"].values, (te["delta_60m"] > 5).values
    
    print(f"\n=== {H}h | Teste: {len(te)} ===")
    print(f"zero            geral={rmse(yt, 0):.2f} subida={rmse(yt[sub], 0):.2f}")
    
    for nome, cols in (("sem_glofas", base), ("com_glofas", com)):
        P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
                 feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
        dtr = lgb.Dataset(tr[cols], tr["y"])
        dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
        b = lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
        pred = b.predict(te[cols], num_iteration=b.best_iteration)
        print(f"{nome:15s} geral={rmse(yt, pred):.2f} subida={rmse(yt[sub], pred[sub]):.2f}")
