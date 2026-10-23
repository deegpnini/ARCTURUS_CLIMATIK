import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
import json

BASE_DIR = Path(__file__).resolve().parents[2]
df = pd.read_csv(BASE_DIR / "data" / "dataset_1h.csv")
df = df.loc[:, ~df.columns.duplicated()]
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').set_index('timestamp')

# Função de carga da montante
def carregar_montante(codigo, nome_curto, df_principal):
    caminho = BASE_DIR / "cache" / f"ana_5anos_{codigo}.json"
    if not caminho.exists(): return pd.Series(dtype=float)
    with open(caminho, "r") as f:
        dados = json.load(f)
    m_df = pd.DataFrame(dados)
    m_df['Data_Hora_Medicao'] = pd.to_datetime(m_df['Data_Hora_Medicao'])
    m_df['cota'] = pd.to_numeric(m_df['Cota_Adotada'], errors='coerce')
    m_df = m_df.set_index('Data_Hora_Medicao').sort_index()
    s = m_df['cota'].resample('1h').last()
    s_delta = s.diff()
    # Pega o lag de 2h (asof)
    dt_2h = df_principal.index - pd.Timedelta(hours=2)
    serie = s_delta.asof(dt_2h)
    serie.index = df_principal.index
    return serie.fillna(0.0)

print("Alinhando montante por TEMPO (asof)...")
df['sao_mauricio_delta_1h_lag2h'] = carregar_montante("84538500", "sao_mauricio", df)
df['rio_fortuna_delta_1h_lag2h'] = carregar_montante("84535000", "rio_fortuna", df)
df['invernadinha_delta_1h_lag2h'] = carregar_montante("70110000", "invernadinha", df)

features_montante = ['sao_mauricio_delta_1h_lag2h', 'rio_fortuna_delta_1h_lag2h', 'invernadinha_delta_1h_lag2h']
features_base = [c for c in df.columns if c not in features_montante and c not in ['target_1h', 'target_3h', 'target_6h', 'target', 'vazao', 'target_1h_real']]
features_finais = features_base + features_montante

# Loop para os 3 horizontes
for h in ['1h', '3h', '6h']:
    # O target é a cota daqui a h horas (shift de horas, não de linhas)
    horas = int(h.replace('h', ''))
    # Se 1h = 4 linhas, 3h = 12, 6h = 24 (mas se houver gap, o shift de tempo é melhor)
    # Vou usar o shift de linhas, mas considerando a base de 15min
    linhas = horas * 4
    df[f'target_{h}_real'] = df['cota'].shift(-linhas) - df['cota']
    # Limpar outliers
    df[f'target_{h}_real'] = df[f'target_{h}_real'].where(df[f'target_{h}_real'].abs() < 200, np.nan)
    
    alvo = f'target_{h}_real'
    treino = df[df.index < '2025-07-01'].dropna(subset=[alvo])
    teste = df[df.index >= '2025-07-01'].dropna(subset=[alvo])
    
    print(f"\nTreinando modelo {h}...")
    m = lgb.LGBMRegressor(n_estimators=156, random_state=42, verbose=-1)
    m.fit(treino[features_finais], treino[alvo])
    
    pred = m.predict(teste[features_finais])
    rmse = np.sqrt(np.mean((teste[alvo] - pred)**2))
    print(f"  RMSE {h}: {rmse:.2f} cm")
    
    # Salvar
    caminho = BASE_DIR / "modelos" / f"modelo_delta_{h}_com_montante.txt"
    m.booster_.save_model(str(caminho))
    print(f"  ✅ Salvo: {caminho}")

print("\n✅ Todos os modelos v2 (1h, 3h, 6h) foram treinados e salvos.")
