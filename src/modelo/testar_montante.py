import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_squared_error, r2_score
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
df = pd.read_csv(BASE_DIR / "data" / "dataset_1h_com_montante.csv")
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').set_index('timestamp')
df = df.loc[:, ~df.columns.duplicated()]

# --- A MÁGICA DO TEMPO DE VIAGEM (LAGS) ---
# Vamos criar versões atrasadas dos deltas de montante (1h, 3h, 6h)
for estacao in ['sao_mauricio', 'rio_fortuna', 'invernadinha']:
    col_delta = f'{estacao}_delta_1h'
    if col_delta in df.columns:
        df[f'{col_delta}_lag3h'] = df[col_delta].shift(3)
        df[f'{col_delta}_lag6h'] = df[col_delta].shift(6)

features_montante = ['sao_mauricio_delta_1h', 'sao_mauricio_delta_1h_lag3h', 'sao_mauricio_delta_1h_lag6h',
                     'rio_fortuna_delta_1h', 'rio_fortuna_delta_1h_lag3h', 'rio_fortuna_delta_1h_lag6h',
                     'invernadinha_delta_1h', 'invernadinha_delta_1h_lag3h', 'invernadinha_delta_1h_lag6h']

# Antigas (sem as montantes para o modelo base)
todas_montantes = [c for c in df.columns if 'montante' in c or 'sao_mauricio' in c or 'rio_fortuna' in c or 'invernadinha' in c]
features_antigas = [c for c in df.columns if c not in todas_montantes and c not in ['target_1h', 'target_3h', 'target_6h', 'target']]
features_novas = features_antigas + features_montante

alvo = 'target_1h'

corte = '2025-01-01'
treino = df[df.index < corte].dropna(subset=[alvo])
teste = df[df.index >= corte].dropna(subset=[alvo])

print(f"Treino: {len(treino)} | Teste: {len(teste)}")

# Modelo Antigo
m_antigo = lgb.LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
m_antigo.fit(treino[features_antigas], treino[alvo])
rmse_antigo = np.sqrt(mean_squared_error(teste[alvo], m_antigo.predict(teste[features_antigas])))

# Modelo Novo (com lags)
m_novo = lgb.LGBMRegressor(n_estimators=100, random_state=42, verbose=-1)
m_novo.fit(treino[features_novas], treino[alvo])
rmse_novo = np.sqrt(mean_squared_error(teste[alvo], m_novo.predict(teste[features_novas])))

print("\n=== RESULTADO DO TESTE A/B COM LAGS ===")
print(f"Modelo Antigo | RMSE: {rmse_antigo:.2f}")
print(f"Modelo Novo   | RMSE: {rmse_novo:.2f}")
print(f"Melhoria      | {rmse_antigo - rmse_novo:.2f} cm")

print("\nTop 10 features (mostrando se os lags subiram):")
importancias = pd.DataFrame({'feature': features_novas, 'importancia': m_novo.feature_importances_}).sort_values('importancia', ascending=False)
print(importancias.head(10).to_string(index=False))
