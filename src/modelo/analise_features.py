import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# Carregar a série da ANA
s = pd.read_csv(BASE / "data" / "ana_longa84580000.csv")
s.columns = ["data", "cota"]
s["data"] = pd.to_datetime(s["data"], errors="coerce")
s["cota"] = pd.to_numeric(s["cota"], errors="coerce")
s = s.dropna(subset=["data"]).drop_duplicates("data").set_index("data").sort_index()
c = s["cota"].asfreq("D")

# Carregar a chuva longa
ch = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
                for f in sorted((BASE / "data").glob("chuva_longa_*.csv"))], axis=1).reindex(c.index)
bacia = ch.mean(axis=1)

# Criar features (incluindo as sugeridas pelo engenheiro)
X = pd.DataFrame(index=c.index)
X["cota"] = c
X["d1"], X["d3"] = c - c.shift(1), c - c.shift(3)
X["max3"] = c.rolling(3, min_periods=3).max()
X["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
X["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
for k in (1, 2, 3, 5, 10, 30):
    X[f"chuva_{k}d"] = bacia.rolling(k, min_periods=k).sum()
X["chuva_max_ponto_2d"] = ch.rolling(2, min_periods=2).sum().max(axis=1)
X["chuva_24h"] = bacia.rolling(1, min_periods=1).sum()
X["chuva_72h"] = bacia.rolling(3, min_periods=3).sum()
X["chuva_7d"] = bacia.rolling(7, min_periods=7).sum()
X["persistencia"] = c.shift(1)  # Cota de ontem
X["tendencia"] = c - c.shift(7)  # Tendência de 7 dias

# Alvo
LIM = 300
fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna())
D = X.join(y.rename("y"))
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])

# Treinar o modelo (com todas as features)
features = [col for col in D.columns if col != "y"]
P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
dtr = lgb.Dataset(D[features], D["y"])
b = lgb.train(P, dtr, 500)

# Importância das features
importancia = pd.DataFrame({"feature": features, "importancia": b.feature_importance()})
importancia = importancia.sort_values("importancia", ascending=False)
print("=== IMPORTÂNCIA DAS FEATURES ===")
print(importancia.to_string(index=False))
