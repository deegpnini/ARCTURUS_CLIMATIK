import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from sklearn.metrics import roc_auc_score

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a série longa (cota)
s = pd.read_csv(BASE / "data" / "ana_longa84580000.csv")
s.columns = ["data", "cota"]
s["data"] = pd.to_datetime(s["data"], errors="coerce")
s["cota"] = pd.to_numeric(s["cota"], errors="coerce")
s = s.dropna(subset=["data"]).drop_duplicates("data").set_index("data").sort_index()
c = s["cota"].asfreq("D")

# 2. Carregar a previsão de chuva (Open-Meteo Forecast)
# O arquivo tem a previsão para os próximos 7 dias (a partir de hoje)
caminho_previsao = BASE / "data" / "previsao_chuva_bacia.csv"
if caminho_previsao.exists():
    prev = pd.read_csv(caminho_previsao, index_col=0, parse_dates=True)
    prev = prev["chuva_prevista_mm"]
    print(f"Previsão de chuva: {len(prev)} horas | Total: {prev.sum():.1f} mm")
else:
    print("❌ Arquivo de previsão não encontrado. Rode baixar_previsao_chuva.py primeiro.")
    exit()

# 3. Carregar a chuva observada (Open-Meteo histórico)
ch = pd.concat([pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
                for f in sorted((BASE / "data").glob("chuva_longa_*.csv"))], axis=1).reindex(c.index)
bacia_obs = ch.mean(axis=1)

# 4. Criar as features
X = pd.DataFrame(index=c.index)
X["cota"] = c
X["d1"], X["d3"] = c - c.shift(1), c - c.shift(3)
X["max3"] = c.rolling(3, min_periods=3).max()
X["sin"] = np.sin(2 * np.pi * c.index.dayofyear / 365.25)
X["cos"] = np.cos(2 * np.pi * c.index.dayofyear / 365.25)
for k in (1, 2, 3, 5, 10, 30):
    X[f"chuva_obs_{k}d"] = bacia_obs.rolling(k, min_periods=k).sum()

# 5. Alvo: cheia em 2 dias (média diária >= 300)
LIM = 300
fut = pd.concat([c.shift(-1), c.shift(-2)], axis=1).max(axis=1, skipna=False)
y = (fut >= LIM).astype(float).where(fut.notna())

# 6. Juntar e limpar
D = X.join(y.rename("y"))
D = D[D["cota"] < LIM].dropna(subset=["y", "cota", "d1", "d3", "max3"])

# 7. Split cronológico
tr = D[D.index < "2000-01-01"]
va = D[(D.index >= "2000-01-01") & (D.index < "2010-01-01")]
te = D[D.index >= "2010-01-01"]

print(f"Treino: {len(tr)} | Validação: {len(va)} | Teste: {len(te)}")
print(f"Eventos no teste: {int(te['y'].sum())}")

# 8. Treinar o classificador (só com chuva observada)
features_obs = [c for c in D.columns if c != "y"]
P = dict(objective="binary", metric="average_precision", learning_rate=0.03, num_leaves=15,
         min_data_in_leaf=50, feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=42, verbose=-1)
dtr = lgb.Dataset(tr[features_obs], tr["y"])
dva = lgb.Dataset(va[features_obs], va["y"], reference=dtr)
b = lgb.train(P, dtr, 2000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])
pred = b.predict(te[features_obs], num_iteration=b.best_iteration)
auc = roc_auc_score(te["y"], pred)
print(f"\n=== Classificador (chuva observada) ===")
print(f"AUC-ROC: {auc:.4f}")

# 9. Simular o classificador com a previsão de chuva
# Para simular, a gente usa a previsão de chuva como se fosse a chuva observada
# (O modelo foi treinado com chuva observada, mas a distribuição é parecida)
previsao_2d = prev.rolling(2).sum().iloc[-1] if len(prev) >= 2 else 0
print(f"\n=== Simulação com Previsão de Chuva ===")
print(f"Chuva prevista para 2 dias: {previsao_2d:.1f} mm")
print(f"(O modelo foi treinado com chuva observada. A previsão é uma aproximação.)")
