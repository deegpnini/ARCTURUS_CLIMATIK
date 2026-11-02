import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a série longa (para treinar o classificador)
s = pd.read_csv(BASE / "data" / "ana_longa84580000.csv")
s.columns = ["data", "cota"]
s["data"] = pd.to_datetime(s["data"], errors="coerce")
s["cota"] = pd.to_numeric(s["cota"], errors="coerce")
s = s.dropna(subset=["data"]).drop_duplicates("data").set_index("data").sort_index()
c = s["cota"].asfreq("D")

# 2. Carregar a chuva observada (histórico)
ch = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
                for f in sorted((BASE / "data").glob("chuva_longa_*.csv"))], axis=1).reindex(c.index)
bacia_obs = ch.mean(axis=1)

# 3. Criar features de treino
X = pd.DataFrame(index=c.index)
X["cota"] = c
X["d1"], X["d3"] = c - c.shift(1), c - c.shift(3)
X["max3"] = c.rolling(3, min_periods=3).max()
X["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
X["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
for k in (1, 2, 3, 5, 10, 30):
    X[f"chuva_{k}d"] = bacia_obs.rolling(k, min_periods=k).sum()

# 4. Alvo: cheia em 2 dias (média diária >= 300)
LIM = 300
fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna())
D = X.join(y.rename("y"))
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])

# 5. Split e treino
tr = D[D.index < "2000-01-01"]
va = D[(D.index >= "2000-01-01") & (D.index < "2010-01-01")]
features = [c for c in D.columns if c != "y"]
P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
dtr = lgb.Dataset(tr[features], tr["y"])
dva = lgb.Dataset(va[features], va["y"], reference=dtr)
b = lgb.train(P, dtr, 2000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])

# 6. Previsão de chuva (48h = 2 dias)
prev = pd.read_csv(BASE / "data" / "previsao_chuva_bacia.csv", index_col=0, parse_dates=True)
prev = prev["chuva_prevista_mm"]
chuva_48h = prev.iloc[:48].sum()  # 56.9 mm
print(f"Chuva prevista para 48h: {chuva_48h:.1f} mm")

# 7. Montar o X para o dia de hoje (24/10/2026)
# Cota atual: 67 cm (do JSON da Tubarão Saneamento)
cota_atual = 67.0
X_hoje = {
    "cota": cota_atual,
    "d1": 0.0,  # Não temos o delta de ontem
    "d3": 0.0,
    "max3": cota_atual,
    "sin": np.sin(2 * np.pi * 297 / 365.25),  # dia 297 do ano
    "cos": np.cos(2 * np.pi * 297 / 365.25),
    "chuva_1d": 0.0,  # Chuva de hoje (não temos)
    "chuva_2d": chuva_48h,  # Chuva das próximas 48h
    "chuva_3d": chuva_48h,
    "chuva_5d": chuva_48h,
    "chuva_10d": chuva_48h,
    "chuva_30d": chuva_48h,
}

# 8. Prever
X_pred = pd.DataFrame([X_hoje])[features]
prob = b.predict(X_pred)[0]
print(f"\n=== SIMULAÇÃO DE ALERTA (24/10/2026) ===")
print(f"Cota atual: {cota_atual:.0f} cm")
print(f"Chuva prevista (48h): {chuva_48h:.1f} mm")
print(f"Probabilidade de cheia (>= 300 cm): {prob:.2%}")
if prob > 0.1:
    print("🚨 ALERTA: Probabilidade de cheia elevada!")
else:
    print("✅ Sem sinal de cheia iminente.")
