import pandas as pd
import numpy as np
import lightgbm as lgb
from sklearn.metrics import mean_squared_error
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
df = pd.read_csv(BASE_DIR / "data" / "dataset_1h_com_montante.csv")
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').set_index('timestamp')
df = df.loc[:, ~df.columns.duplicated()]

# Criando múltiplos lags para testar o tempo de viagem real
for estacao in ['sao_mauricio', 'rio_fortuna', 'invernadinha']:
    col_delta = f'{estacao}_delta_1h'
    if col_delta in df.columns:
        for lag in [1, 2, 3, 6, 12]:
            df[f'{col_delta}_lag{lag}h'] = df[col_delta].shift(lag)

alvo = 'target_1h'

# O Split correto (conforme dataset original)
# Vamos usar datas fixas para garantir o volume de treino
treino = df[df.index < '2025-07-01'].dropna(subset=[alvo])
teste = df[df.index >= '2025-07-01'].dropna(subset=[alvo])

print(f"Treino: {len(treino)} | Teste: {len(teste)}")

todas_montantes = [c for c in df.columns if 'sao_mauricio' in c or 'rio_fortuna' in c or 'invernadinha' in c]
features_antigas = [c for c in df.columns if c not in todas_montantes and c not in ['target_1h', 'target_3h', 'target_6h', 'target']]

def treinar_avaliar(features_novas, nome):
    m = lgb.LGBMRegressor(n_estimators=150, random_state=42, verbose=-1)
    m.fit(treino[features_novas], treino[alvo])
    
    # Avaliar apenas em momentos de SUBIDA (onde a cota atual subiu mais de 5cm)
    mask_subida = teste['delta_60m'] > 5
    teste_subida = teste[mask_subida]
    
    if len(teste_subida) == 0:
        return None
        
    pred = m.predict(teste_subida[features_novas])
    rmse = np.sqrt(mean_squared_error(teste_subida[alvo], pred))
    print(f"{nome:20s} | RMSE (na subida): {rmse:.2f} cm")
    return m

print("\n=== TESTE A/B (Focado em SUBIDAS) ===")
m_base = treinar_avaliar(features_antigas, "Modelo Antigo (base)")

lags_para_testar = [1, 2, 3, 6, 12]
for lag in lags_para_testar:
    features_lag = features_antigas + [f'{e}_delta_1h_lag{lag}h' for e in ['sao_mauricio', 'rio_fortuna', 'invernadinha'] if f'{e}_delta_1h_lag{lag}h' in df.columns]
    m_lag = treinar_avaliar(features_lag, f"Modelo c/ lag {lag}h")
