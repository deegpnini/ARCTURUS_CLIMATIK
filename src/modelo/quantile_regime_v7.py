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

# Features base (v6)
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

# Chuva da bacia
ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
for lag_h in [4, 6, 8]:
    X[f"bacia_lag_{lag_h}h"] = media.shift(lag_h * 4).reindex(g.index, method="ffill")
for k in (3, 6, 12):
    X[f"bacia_{k}h"] = media.rolling(k, min_periods=k).sum().reindex(g.index, method="ffill")

# Features de intensidade (CORRIGIDAS)
# 1. Máximo da média móvel de 1h (um ponto só, sem ambiguidade)
X["bacia_max1h"] = media.rolling(1, min_periods=1).max().reindex(g.index, method="ffill")
# 2. Quantos pontos chovendo forte (soma > 10mm em 3h)
s3 = ch.rolling(3, min_periods=3).sum()
X["bacia_pontos_forte"] = (s3 > 10).sum(axis=1).reindex(g.index, method="ffill")
# 3. Aceleração da chuva (3h atual vs 3h anterior)
X["aceleracao_chuva"] = (media.rolling(3, min_periods=3).sum() - media.rolling(3, min_periods=3).sum().shift(3)).reindex(g.index, method="ffill")

features = list(X.columns)
print(f"Features: {len(features)}")

# Alvo: delta de 6h
y = (c.shift(-24) - c).rename("y")
D = X.join(y).dropna(subset=["y", "cota"])
tr = D[D.index < "2026-09-01"]
va = D[(D.index >= "2026-01-01") & (D.index < "2026-07-01")]

print(f"Treino: {len(tr)} | Validação: {len(va)}")

# Treinar 3 modelos (quantis)
quantis = {0.50: "Mediana", 0.90: "Alerta", 0.99: "Extremo"}
modelos = {}

for q, nome in quantis.items():
    P = dict(objective="quantile", alpha=q, learning_rate=0.03, num_leaves=15, 
             min_data_in_leaf=100, feature_fraction=0.8, bagging_fraction=0.8, 
             bagging_freq=1, seed=42, verbose=-1)
    dtr = lgb.Dataset(tr[features], tr["y"])
    dva = lgb.Dataset(va[features], va["y"], reference=dtr)
    b = lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
    modelos[q] = b
    print(f"Modelo {nome} (q={q}) treinado. Iterações: {b.best_iteration}")

# Teste no evento 22/09
T0 = pd.date_range("2026-09-21 19:00", "2026-09-21 19:45", freq="15min")
X_test = X.reindex(T0, method="ffill").fillna(0.0)

print(f"\n=== PREVISÃO NO EVENTO DE 22/09 (Subida real: +284 cm) ===")
print(f"{'Emissão':>8} | {'Cota':>5} | {'q50':>8} | {'q90':>8} | {'q99':>8} | {'Real':>8}")
for i, t in enumerate(T0):
    cota_t = X_test.loc[t, "cota"]
    preds = {q: modelos[q].predict(X_test.loc[[t], features])[0] for q in quantis}
    print(f"{t:%H:%M}   | {cota_t:>5.0f} | {preds[0.50]:>+8.1f} | {preds[0.90]:>+8.1f} | {preds[0.99]:>+8.1f} | {284:>+8.0f}")
