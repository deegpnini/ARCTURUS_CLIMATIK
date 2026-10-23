import json
import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent))
from insight_parte2 import carregar_dados_telemetria, reconstruir_features

BASE_DIR = Path(__file__).resolve().parents[2]
MODELOS = BASE_DIR / "modelos"
CACHE = BASE_DIR / "cache"

def obter_delta_montante(codigo, dt_atual, lag_horas=2):
    caminho = CACHE / f"ana_5anos_{codigo}.json"
    if not caminho.exists():
        return 0.0
    with open(caminho, "r") as f:
        dados = json.load(f)
    df = pd.DataFrame(dados)
    df['Data_Hora_Medicao'] = pd.to_datetime(df['Data_Hora_Medicao'])
    df['cota_num'] = pd.to_numeric(df['Cota_Adotada'], errors='coerce')
    df = df.set_index('Data_Hora_Medicao').sort_index()
    df_hora = df['cota_num'].resample('1h').last()
    df_delta = df_hora.diff()
    dt_alvo = dt_atual - pd.Timedelta(hours=lag_horas)
    if df_delta.empty:
        return 0.0
    idx_mais_proximo = df_delta.index.get_indexer([dt_alvo], method='nearest')[0]
    valor = df_delta.iloc[idx_mais_proximo]
    return 0.0 if pd.isna(valor) else float(valor)

def main():
    print("=== ARCTURUS v2: PREVISÃO COM MONTANTE ===")
    
    # Carregar o modelo novo
    caminho_modelo = MODELOS / "modelo_delta_1h_com_montante.txt"
    if not caminho_modelo.exists():
        print("❌ Modelo v2 não encontrado.")
        return
    modelo = lgb.Booster(model_file=str(caminho_modelo))
    
    # Puxar dados vivos
    print("Puxando telemetria local...")
    dados_ana = carregar_dados_telemetria()
    if not dados_ana:
        print("❌ Falha ao carregar telemetria.")
        return
        
    dt_atual = max(dados_ana.keys())
    print(f"Instante atual: {dt_atual}")
    
    # Reconstruir features base
    feats_base = reconstruir_features(dados_ana, dt_atual)
    
    # Injetar as features de montante
    feats_v2 = feats_base.copy()
    feats_v2['sao_mauricio_delta_1h_lag2h'] = obter_delta_montante("84538500", dt_atual, 2)
    feats_v2['rio_fortuna_delta_1h_lag2h'] = obter_delta_montante("84535000", dt_atual, 2)
    feats_v2['invernadinha_delta_1h_lag2h'] = obter_delta_montante("70110000", dt_atual, 2)
    
    # Garantir a vazao (que o modelo espera, mas o script antigo não gera)
    if 'vazao' not in feats_v2:
        feats_v2['vazao'] = 0.0 
        
    # A MÁGICA: Pega a ordem EXATA que o modelo espera
    ordem_correta = modelo.feature_name()
    
    # Cria o X na ordem certa, preenchendo o que faltar com 0.0
    X_lista = [feats_v2.get(f, 0.0) for f in ordem_correta]
    X = np.array([X_lista])
    
    # Prever
    delta_previsto = float(modelo.predict(X)[0])
    # TRAVA DE SEGURANÇA (Método Cético 9.9)
    # Fisicamente, a bacia do Tubarão não sobe mais de 150 cm em 1h.
    delta_previsto = max(min(delta_previsto, 150.0), -150.0)
    cota_atual = feats_v2.get("cota", 0)
    cota_prevista = cota_atual + delta_previsto
    
    print("\n=== RESULTADO (CORRIGIDO) ===")
    print(f"Cota Atual: {cota_atual:.2f} cm")
    print(f"Delta Previsto (1h): {delta_previsto:+.2f} cm")
    print(f"Cota Prevista (1h): {cota_prevista:.2f} cm")
    
    print("\nFeatures de montante usadas:")
    print(f"  São Maurício (lag 2h): {feats_v2['sao_mauricio_delta_1h_lag2h']:+.2f} cm")
    print(f"  Rio Fortuna (lag 2h): {feats_v2['rio_fortuna_delta_1h_lag2h']:+.2f} cm")
    print(f"  Invernadinha (lag 2h): {feats_v2['invernadinha_delta_1h_lag2h']:+.2f} cm")

if __name__ == "__main__":
    main()
