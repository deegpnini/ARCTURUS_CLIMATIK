import json
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

# ========== FEATURES (mesma lógica) ==========
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

ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
for lag_h in [4, 6, 8]:
    X[f"bacia_lag_{lag_h}h"] = media.shift(lag_h * 4).reindex(g.index, method="ffill")
for k in (3, 6, 12):
    X[f"bacia_{k}h"] = media.rolling(k, min_periods=k).sum().reindex(g.index, method="ffill")

features = list(X.columns)
print(f"Features: {len(features)}")

# ========== LEAVE-ONE-OUT ==========
H = 6
n = H * 4
y = (c.shift(-n) - c).rename("y")
D = X.join(y).dropna(subset=["y", "cota"])
tr = D[D.index < "2026-09-01"]
va = D[(D.index >= "2026-01-01") & (D.index < "2026-07-01")]
print(f"Treino: {len(tr)} | Validação: {len(va)}")

P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
         feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
dtr = lgb.Dataset(tr[features], tr["y"])
dva = lgb.Dataset(va[features], va["y"], reference=dtr)
b = lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])

# ========== PONTOS DE TESTE (do cache, não do dataset) ==========
T0 = pd.date_range("2026-09-21 19:00", "2026-09-21 19:45", freq="15min")
X_test = X.reindex(T0, method="ffill")  # Usa o último valor conhecido

# Verificar se as features existem
print(f"\nPontos de teste: {len(X_test)}")
print(f"Cota disponível: {X_test['cota'].notna().sum()} de {len(X_test)}")
print(f"Features com NaN: {X_test.isna().sum().sum()}")

if X_test.isna().any().any():
    print("⚠️ Há features NaN. Vou preencher com 0.0 para o teste.")
    X_test = X_test.fillna(0.0)

# Cota em 19:00
cota_19 = X_test.loc[T0[0], "cota"]
cota_pico = 446.0
print(f"\nCota em 19:00: {cota_19:.0f} cm")
print(f"Cota no pico (446 cm): {cota_pico:.0f} cm")
print(f"Subida real observada: {cota_pico - cota_19:+.0f} cm\n")

pred = b.predict(X_test[features], num_iteration=b.best_iteration)
print(f"{'Emissão':>10} | {'Cota':>5} | {'Previsão 6h':>12} | {'Real':>8} | {'Erro':>8}")
for i, t in enumerate(T0):
    cota_t = X_test.loc[t, "cota"]
    pred_delta = pred[i]
    real_delta = cota_pico - cota_t
    erro = pred_delta - real_delta
    print(f"{t:%H:%M}:   | {cota_t:>5.0f} | {pred_delta:>+12.1f} | {real_delta:>+8.0f} | {erro:>+8.1f}")
