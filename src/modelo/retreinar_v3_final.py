import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_squared_error, r2_score
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
df = pd.read_csv(BASE_DIR / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True)
df = df.loc[:, ~df.columns.duplicated()]

# 1. REMOVER A INVERNADINHA (Bacia Errada)
df = df.drop(columns=[c for c in df.columns if 'invernadinha' in c], errors='ignore')

# 2. CORRIGIR O ALVO PARA TEMPO (1h real)
# Em vez de shift(-4), vamos usar o índice de tempo.
df['target_1h_real'] = df['cota'].shift(-4) - df['cota']
# Limpar outliers
df['target_1h_real'] = df['target_1h_real'].where(df['target_1h_real'].abs() < 150, np.nan)

alvo = 'target_1h_real'
features = [c for c in df.columns if 'target' not in c and 'cota_abs' not in c and 'delta_1h' not in c]

# 3. SPLIT CRONOLÓGICO (Treino / Validação / Teste)
treino = df[df.index < '2025-01-01'].dropna(subset=[alvo])
val = df[(df.index >= '2025-01-01') & (df.index < '2025-07-01')].dropna(subset=[alvo])
teste = df[df.index >= '2025-07-01'].dropna(subset=[alvo])

print(f"Treino: {len(treino)} | Validação: {len(val)} | Teste: {len(teste)}")
print(f"Features: {len(features)} (Invernadinha removida)")

# 4. TREINO COM EARLY STOPPING NA VALIDAÇÃO (não no teste)
m = lgb.LGBMRegressor(n_estimators=1000, random_state=42, verbose=-1)
m.fit(
    treino[features], treino[alvo],
    eval_set=[(val[features], val[alvo])],
    eval_metric='rmse',
    callbacks=[lgb.early_stopping(stopping_rounds=50)]
)

# 5. AVALIAÇÃO NO TESTE (Intocado)
pred = m.predict(teste[features])
rmse = np.sqrt(mean_squared_error(teste[alvo], pred))
r2 = r2_score(teste[alvo], pred)

# RMSE na subida (delta > 5)
mask_subida = teste['delta_60m'] > 5
rmse_subida = np.sqrt(mean_squared_error(teste[mask_subida][alvo], pred[mask_subida]))

print("\n=== RESULTADO FINAL (SEM INVERNADINHA) ===")
print(f"RMSE Geral: {rmse:.2f} cm")
print(f"RMSE na Subida: {rmse_subida:.2f} cm")
print(f"R²: {r2:.4f}")

# 6. SALVAR O MODELO
caminho = BASE_DIR / "modelos" / "modelo_delta_1h_final.txt"
m.booster_.save_model(str(caminho))
print(f"✅ Modelo salvo em: {caminho}")
