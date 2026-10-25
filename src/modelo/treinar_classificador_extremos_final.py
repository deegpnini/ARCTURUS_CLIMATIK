import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
import json

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a série longa (cota diária)
s = pd.read_csv(BASE / "data" / "ana_longa84580000.csv")
s.columns = ["data", "cota"]
s["data"] = pd.to_datetime(s["data"], errors="coerce")
s["cota"] = pd.to_numeric(s["cota"], errors="coerce")
s = s.dropna(subset=["data"]).drop_duplicates("data").set_index("data").sort_index()
c = s["cota"].asfreq("D")

# 2. Carregar a chuva longa (5 pontos)
ch = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
                for f in sorted((BASE / "data").glob("chuva_longa_*.csv"))], axis=1).reindex(c.index)
bacia = ch.mean(axis=1)

# 3. Criar features
X = pd.DataFrame(index=c.index)
X["cota"] = c
X["d1"], X["d3"] = c - c.shift(1), c - c.shift(3)
X["max3"] = c.rolling(3, min_periods=3).max()
X["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
X["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
for k in (1, 2, 3, 5, 10, 30):
    X[f"chuva_{k}d"] = bacia.rolling(k, min_periods=k).sum()
X["chuva_max_ponto_2d"] = ch.rolling(2, min_periods=2).sum().max(axis=1)

# 4. Alvo: cheia em 2 dias (média diária >= 300)
LIM = 300
fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna())
D = X.join(y.rename("y"))
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])

# 5. Treinar com TODOS os dados (1939-2026)
features = [c for c in D.columns if c != "y"]
P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
dtr = lgb.Dataset(D[features], D["y"])
b = lgb.train(P, dtr, 2000)

# 6. Salvar o modelo e o manifesto
caminho_modelo = BASE / "modelos" / "classificador_extremos_final.txt"
b.save_model(str(caminho_modelo))
print(f"✅ Modelo salvo em: {caminho_modelo}")

manifesto = {
    "features": features,
    "n_features": len(features),
    "limiar_cheia": LIM,
    "total_eventos": int(D["y"].sum()),
    "total_dias": len(D),
    "data_treino": str(D.index.min()),
    "data_teste": str(D.index.max()),
}
with open(BASE / "modelos" / "manifesto_classificador_extremos.json", "w") as f:
    json.dump(manifesto, f, indent=2)
print(f"✅ Manifesto salvo.")
print(f"   Total de eventos: {int(D['y'].sum())} de {len(D)} dias.")
