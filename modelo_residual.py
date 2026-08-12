# ============================================================
# ARCTURUS CLIMATIK — MODELO RESIDUAL (v2.0)
# ============================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error
import joblib
import warnings
warnings.filterwarnings("ignore")

print("🚀 ARCTURUS CLIMATIK — MODELO RESIDUAL (v2.0)")
print("="*60)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
DATA_PATH = "dados/arcturus_climatik_final_limpo.csv"
MODEL_PATH = "modelos/modelo_residual.pkl"

import os
os.makedirs("modelos", exist_ok=True)

# ============================================================
# CARREGAR DADOS
# ============================================================
print("\n📂 Carregando dados...")

if not os.path.exists(DATA_PATH):
    print(f"⚠️ Arquivo não encontrado: {DATA_PATH}")
    print("   Usando fallback: /content/arcturus_climatik_final_limpo.csv")
    DATA_PATH = "/content/arcturus_climatik_final_limpo.csv"

df = pd.read_csv(DATA_PATH)
df["data_hora"] = pd.to_datetime(df["data_hora"])
df = df.sort_values(["id_estacao_final", "data_hora"])

print(f"✅ {df.shape[0]:,} registros")

# ============================================================
# FEATURES E ALVO
# ============================================================
print("\n🔧 Criando features...")

df['temp_lag_1'] = df.groupby('id_estacao_final')['temperatura'].shift(1)
df['temp_lag_3'] = df.groupby('id_estacao_final')['temperatura'].shift(3)
df['temp_lag_6'] = df.groupby('id_estacao_final')['temperatura'].shift(6)
df['temp_lag_12'] = df.groupby('id_estacao_final')['temperatura'].shift(12)

df['residual'] = df['temperatura'] - df['temp_lag_1']

df['hora'] = df['data_hora'].dt.hour
df['mes'] = df['data_hora'].dt.month
df['dia_semana'] = df['data_hora'].dt.dayofweek

df['hora_sin'] = np.sin(2 * np.pi * df['hora'] / 24)
df['hora_cos'] = np.cos(2 * np.pi * df['hora'] / 24)
df['mes_sin'] = np.sin(2 * np.pi * df['mes'] / 12)
df['mes_cos'] = np.cos(2 * np.pi * df['mes'] / 12)

df['umidade_imputada'] = df.groupby('id_estacao_final')['umidade'].transform(lambda x: x.fillna(x.mean()))
df['umidade_flag'] = df['umidade'].isna().astype(int)

df = df.dropna(subset=['temperatura', 'temp_lag_1', 'residual'])
print(f"✅ Limpo: {df.shape[0]:,} registros")

# ============================================================
# SPLIT TEMPORAL
# ============================================================
print("\n📊 Split temporal...")

df_train = df[df['data_hora'] < '2026-01-01']
df_test = df[df['data_hora'] >= '2026-01-01']

print(f"  Treino: {df_train.shape[0]:,}")
print(f"  Teste: {df_test.shape[0]:,}")

# ============================================================
# FEATURES
# ============================================================
feature_cols = [
    'hora_sin', 'hora_cos', 'mes_sin', 'mes_cos', 'dia_semana',
    'temp_lag_3', 'temp_lag_6', 'temp_lag_12',
    'umidade_imputada', 'umidade_flag'
]

X_train = df_train[feature_cols].fillna(0)
y_train = df_train['residual']

X_test = df_test[feature_cols].fillna(0)
y_test = df_test['residual']

y_pers = df_test['temp_lag_1'].values
y_true = df_test['temperatura'].values

# ============================================================
# TREINAMENTO
# ============================================================
print("\n🧠 Treinando Random Forest residual...")

rf = RandomForestRegressor(
    n_estimators=150,
    max_depth=12,
    min_samples_leaf=5,
    n_jobs=-1,
    random_state=42
)
rf.fit(X_train, y_train)

# ============================================================
# AVALIAÇÃO
# ============================================================
print("\n📊 Avaliando...")

residual_pred = rf.predict(X_test)
temp_pred = y_pers + residual_pred

rmse_model = np.sqrt(mean_squared_error(y_true, temp_pred))
mae_model = mean_absolute_error(y_true, temp_pred)

rmse_pers = np.sqrt(mean_squared_error(y_true, y_pers))
mae_pers = mean_absolute_error(y_true, y_pers)

skill_rmse = 1 - (rmse_model / rmse_pers)
skill_mae = 1 - (mae_model / mae_pers)

print(f"\n📊 RESULTADOS:")
print(f"  RMSE modelo: {rmse_model:.3f}°C")
print(f"  RMSE persistência: {rmse_pers:.3f}°C")
print(f"  Skill RMSE: {skill_rmse:.3f}")
print(f"  Skill MAE: {skill_mae:.3f}")

# ============================================================
# SALVAR MODELO
# ============================================================
joblib.dump(rf, MODEL_PATH)
print(f"\n✅ Modelo salvo: {MODEL_PATH}")

print("\n" + "="*60)
print("✅ MODELO RESIDUAL CONCLUÍDO")
print("="*60)