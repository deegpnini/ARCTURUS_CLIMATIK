import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]

# 1. Carregar o dataset e garantir que o tempo está certo
df = pd.read_csv(BASE_DIR / "data" / "dataset_1h.csv") # Começa do original (sem montante)
df = df.loc[:, ~df.columns.duplicated()]
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').set_index('timestamp')

# Recalcular o target_1h por TEMPO (não por linha)
# O target é a cota daqui a 1h (60 min) menos a cota atual.
# Como os dados são de 15 em 15 min, 1h = 4 linhas.
# Mas se houver gap, a gente pega o próximo valor disponível.
df['target_1h_real'] = df['cota'].shift(-4) - df['cota']
df['target_1h_real'] = df['target_1h_real'].where(df['target_1h_real'].abs() < 150, np.nan) # Descarta outliers > 150

# 2. Trazer a montante usando o motor de tempo (asof)
def carregar_montante(codigo, nome_curto):
    caminho = BASE_DIR / "cache" / f"ana_5anos_{codigo}.json"
    if not caminho.exists(): return pd.Series(dtype=float)
    with open(caminho, "r") as f:
        dados = json.load(f)
    m_df = pd.DataFrame(dados)
    m_df['Data_Hora_Medicao'] = pd.to_datetime(m_df['Data_Hora_Medicao'])
    m_df['cota'] = pd.to_numeric(m_df['Cota_Adotada'], errors='coerce')
    m_df = m_df.set_index('Data_Hora_Medicao').sort_index()
    
    # Delta da montante (variação de 1h)
    s = m_df['cota'].resample('1h').last()
    s_delta = s.diff()
    
    # Traz para o tempo do dataset principal (o valor de 2h atrás)
    dt_2h = df.index - pd.Timedelta(hours=2)
    # Usa asof para pegar o valor mais recente no passado
    serie_alinhada = s_delta.asof(dt_2h)
    serie_alinhada.index = df.index
    return serie_alinhada.fillna(0.0)

print("Alinhando montante por TEMPO (asof)...")
df['sao_mauricio_delta_1h_lag2h'] = carregar_montante("84538500", "sao_mauricio")
df['rio_fortuna_delta_1h_lag2h'] = carregar_montante("84535000", "rio_fortuna")
df['invernadinha_delta_1h_lag2h'] = carregar_montante("70110000", "invernadinha")

# 3. Definir features (remover as antigas e o target velho)
features_montante = ['sao_mauricio_delta_1h_lag2h', 'rio_fortuna_delta_1h_lag2h', 'invernadinha_delta_1h_lag2h']
features_base = [c for c in df.columns if c not in features_montante and c not in ['target_1h', 'target_1h_real', 'target_3h', 'target_6h', 'target', 'vazao']]
features_finais = features_base + features_montante

# 4. Split e Treino
alvo = 'target_1h_real'
treino = df[df.index < '2025-07-01'].dropna(subset=[alvo])
teste = df[df.index >= '2025-07-01'].dropna(subset=[alvo])

print(f"Treino: {len(treino)} | Teste: {len(teste)}")
print(f"Features: {len(features_finais)}")

# 5. Treinar
m = lgb.LGBMRegressor(n_estimators=156, random_state=42, verbose=-1)
m.fit(treino[features_finais], treino[alvo])

pred = m.predict(teste[features_finais])
rmse = np.sqrt(np.mean((teste[alvo] - pred)**2))
mask_subida = teste['delta_60m'] > 5
rmse_subida = np.sqrt(np.mean((teste[mask_subida][alvo] - pred[mask_subida])**2))

print(f"RMSE Geral: {rmse:.2f} cm")
print(f"RMSE na Subida: {rmse_subida:.2f} cm")

# 6. Salvar
caminho_modelo = BASE_DIR / "modelos" / "modelo_delta_1h_com_montante.txt"
m.booster_.save_model(str(caminho_modelo))
print(f"✅ Modelo salvo em: {caminho_modelo}")

manifesto = {
    "features": features_finais,
    "n_features": len(features_finais),
    "rmse_geral": float(rmse),
    "rmse_subida": float(rmse_subida)
}
with open(BASE_DIR / "modelos" / "manifesto_montante.json", "w") as f:
    json.dump(manifesto, f, indent=4)
print("✅ Manifesto atualizado.")
