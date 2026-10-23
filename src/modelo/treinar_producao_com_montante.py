import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
df = pd.read_csv(BASE_DIR / "data" / "dataset_1h_com_montante.csv")
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').set_index('timestamp')
df = df.loc[:, ~df.columns.duplicated()]

# Criar os lags de 2h para as estações de montante
for estacao in ['sao_mauricio', 'rio_fortuna', 'invernadinha']:
    col = f'{estacao}_delta_1h'
    if col in df.columns:
        df[f'{col}_lag2h'] = df[col].shift(2)

alvo = 'target_1h'
features_montante = ['sao_mauricio_delta_1h_lag2h', 'rio_fortuna_delta_1h_lag2h', 'invernadinha_delta_1h_lag2h']

# Filtrar features (remover as montantes originais e focar nas com lag)
todas_montantes_orig = [c for c in df.columns if 'sao_mauricio' in c or 'rio_fortuna' in c or 'invernadinha' in c]
features_base = [c for c in df.columns if c not in todas_montantes_orig and c not in ['target_1h', 'target_3h', 'target_6h', 'target']]

features_finais = features_base + features_montante

# Split: Treino até 2025-07, Teste depois
treino = df[df.index < '2025-07-01'].dropna(subset=[alvo, features_montante[-1]])
teste = df[df.index >= '2025-07-01'].dropna(subset=[alvo, features_montante[-1]])

print(f"Treinando modelo de produção com {len(features_finais)} features...")
m = lgb.LGBMRegressor(n_estimators=156, random_state=42, verbose=-1)
m.fit(treino[features_finais], treino[alvo])

# Avaliar no geral
pred = m.predict(teste[features_finais])
rmse_geral = np.sqrt(np.mean((teste[alvo] - pred)**2))
print(f"RMSE Geral (teste): {rmse_geral:.2f} cm")

# Avaliar na subida
mask_subida = teste['delta_60m'] > 5
rmse_subida = np.sqrt(np.mean((teste[mask_subida][alvo] - pred[mask_subida])**2))
print(f"RMSE na Subida: {rmse_subida:.2f} cm")

# Salvar o modelo treinado (Opcional, para o artefato de produção)
caminho_modelo = BASE_DIR / "modelos" / "modelo_delta_1h_com_montante.txt"
m.booster_.save_model(str(caminho_modelo))
print(f"✅ Modelo salvo em: {caminho_modelo}")

# Salvar o manifesto
manifesto = {
    "features": features_finais,
    "n_features": len(features_finais),
    "rmse_geral": float(rmse_geral),
    "rmse_subida": float(rmse_subida),
    "data_treino": str(treino.index.min()),
    "data_teste": str(teste.index.max())
}
with open(BASE_DIR / "modelos" / "manifesto_montante.json", "w") as f:
    json.dump(manifesto, f, indent=4)
print("✅ Manifesto salvo.")
