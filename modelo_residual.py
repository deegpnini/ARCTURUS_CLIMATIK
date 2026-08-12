# ============================================================
# ARCTURUS CLIMATIK — MODELO RESIDUAL
# ============================================================
# Modelo que prevê o residual (ΔT) da persistência
# ============================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
from sklearn.model_selection import TimeSeriesSplit
import warnings
warnings.filterwarnings('ignore')

print("🚀 ARCTURUS CLIMATIK — MODELO RESIDUAL")
print("="*60)

# ============================================================
# CARREGAR DADOS
# ============================================================
df = pd.read_csv('/content/arcturus_climatik_final_limpo.csv')
df['data_hora'] = pd.to_datetime(df['data_hora'])
df = df.sort_values(['id_estacao', 'data_hora'])

print(f"✅ Dataset: {df.shape[0]:,} registros")

# ============================================================
# CRIAR FEATURES E RESIDUAL
# ============================================================
print("\n🔧 CRIANDO FEATURES...")

# Lags
df['temp_lag_1'] = df.groupby('id_estacao')['temperatura'].shift(1)
df['temp_lag_3'] = df.groupby('id_estacao')['temperatura'].shift(3)
df['temp_lag_6'] = df.groupby('id_estacao')['temperatura'].shift(6)
df['temp_lag_12'] = df.groupby('id_estacao')['temperatura'].shift(12)

# Residual (ALVO)
df['residual'] = df['temperatura'] - df['temp_lag_1']

# Features temporais
df['hora'] = df['data_hora'].dt.hour
df['mes'] = df['data_hora'].dt.month
df['dia_semana'] = df['data_hora'].dt.dayofweek

df['hora_sin'] = np.sin(2 * np.pi * df['hora'] / 24)
df['hora_cos'] = np.cos(2 * np.pi * df['hora'] / 24)
df['mes_sin'] = np.sin(2 * np.pi * df['mes'] / 12)
df['mes_cos'] = np.cos(2 * np.pi * df['mes'] / 12)

# Umidade
df['umidade_imputada'] = df.groupby('id_estacao')['umidade'].transform(lambda x: x.fillna(x.mean()))
df['umidade_flag'] = df['umidade'].isna().astype(int)

df = df.dropna(subset=['temperatura', 'temp_lag_1', 'residual'])
print(f"✅ Limpo: {df.shape[0]:,} registros")

# ============================================================
# TREINAR E AVALIAR
# ============================================================
print("\n🧠 TREINANDO MODELO RESIDUAL...")

# Split temporal
df_train = df[df['data_hora'] < '2026-01-01']
df_test = df[df['data_hora'] >= '2026-01-01']

feature_cols = ['hora_sin', 'hora_cos', 'mes_sin', 'mes_cos', 'dia_semana',
                'temp_lag_1', 'temp_lag_3', 'temp_lag_6', 'temp_lag_12',
                'umidade_imputada', 'umidade_flag']

X_train = df_train[feature_cols].fillna(0)
y_train = df_train['residual']
X_test = df_test[feature_cols].fillna(0)

rf = RandomForestRegressor(n_estimators=100, max_depth=10, random_state=42, n_jobs=-1)
rf.fit(X_train, y_train)

# Predição
residual_pred = rf.predict(X_test)
temp_pred = df_test['temp_lag_1'].values + residual_pred
y_true = df_test['temperatura'].values

# Métricas
rmse_model = np.sqrt(mean_squared_error(y_true, temp_pred))
mae_model = mean_absolute_error(y_true, temp_pred)

rmse_pers = np.sqrt(mean_squared_error(y_true, df_test['temp_lag_1'].values))
mae_pers = mean_absolute_error(y_true, df_test['temp_lag_1'].values)

skill_rmse = 1 - (rmse_model / rmse_pers)
skill_mae = 1 - (mae_model / mae_pers)

print(f"\n📊 RESULTADOS:")
print(f"  RMSE Modelo: {rmse_model:.3f}°C")
print(f"  RMSE Persistência: {rmse_pers:.3f}°C")
print(f"  Skill RMSE: {skill_rmse:.3f}")
print(f"  Skill MAE: {skill_mae:.3f}")

print("\n" + "="*60)
print("✅ MODELO RESIDUAL CONCLUÍDO")
print("="*60)
