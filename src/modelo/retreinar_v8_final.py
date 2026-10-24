import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
import json

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar o dataset
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True)
raw = raw.loc[:, ~raw.columns.duplicated()]
raw = raw.sort_index()
raw = raw[~raw.index.duplicated(keep="last")]

# 2. Remover a Invernadinha (bacia errada)
colunas_remover = [c for c in raw.columns if 'invernadinha' in c]
raw = raw.drop(columns=colunas_remover, errors='ignore')
print(f"Colunas removidas: {colunas_remover}")

# 3. Recalcular as features com grade regular de 15min (corrige o alvo)
g = raw.resample("15min").last()
c = g["cota"]

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

# Chuva da bacia (com lags)
ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
for lag_h in [4, 6, 8]:
    X[f"bacia_lag_{lag_h}h"] = media.shift(lag_h * 4).reindex(g.index, method="ffill")
for k in (3, 6, 12):
    X[f"bacia_{k}h"] = media.rolling(k, min_periods=k).sum().reindex(g.index, method="ffill")
X["bacia_max1h"] = media.rolling(1, min_periods=1).max().reindex(g.index, method="ffill")
X["bacia_pontos_forte"] = (ch.rolling(3, min_periods=3).sum() > 10).sum(axis=1).reindex(g.index, method="ffill")

h = g.index.hour + g.index.minute / 60
X["sin_hora"] = np.sin(2 * np.pi * h / 24)
X["cos_hora"] = np.cos(2 * np.pi * h / 24)
d = g.index.dayofyear / 365.0
X["sin_dia_ano"] = np.sin(2 * np.pi * d)
X["cos_dia_ano"] = np.cos(2 * np.pi * d)

features = list(X.columns)
print(f"Features finais: {len(features)}")

# 4. Treinar os modelos com alvo por tempo
for H, n in ((1, 4), (3, 12), (6, 24)):
    y = (c.shift(-n) - c).rename("y")
    D = X.join(y).dropna(subset=["y", "cota"])
    tr = D[D.index < "2025-01-01"]
    va = D[(D.index >= "2025-01-01") & (D.index < "2025-07-01")]
    te = D[D.index >= "2025-07-01"]
    
    P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
             feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
    dtr = lgb.Dataset(tr[features], tr["y"])
    dva = lgb.Dataset(va[features], va["y"], reference=dtr)
    b = lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
    
    pred = b.predict(te[features], num_iteration=b.best_iteration)
    rmse = np.sqrt(np.mean((te["y"] - pred)**2))
    mask_subida = te["delta_60m"] > 5
    rmse_subida = np.sqrt(np.mean((te[mask_subida]["y"] - pred[mask_subida])**2))
    
    caminho = BASE / "modelos" / f"modelo_delta_{H}h_v8_final.txt"
    b.save_model(str(caminho), num_iteration=b.best_iteration)
    print(f"Modelo {H}h salvo. RMSE Geral: {rmse:.2f} | RMSE Subida: {rmse_subida:.2f}")

# 5. Salvar o manifesto
manifesto = {"features": features, "n_features": len(features), "versao": "v8_final", 
             "invernadinha_removida": True, "alvo_por_tempo": True}
with open(BASE / "modelos" / "manifesto_v8.json", "w") as f:
    json.dump(manifesto, f, indent=2)
print("Manifesto v8 salvo.")
