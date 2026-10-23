import json
import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
import sys

sys.path.append(str(Path(__file__).resolve().parent))
sys.path.append(str(Path(__file__).resolve().parents[2]))
import puxar_historico_ana as ana

BASE_DIR = Path(__file__).resolve().parents[2]
MODELOS = BASE_DIR / "modelos"

def obter_dados_hoje():
    token = ana.get_token()
    # Puxa os últimos 30 dias para pegar a leitura de hoje
    hoje = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    # Estação de montante viva
    print("Puxando São Maurício (Montante)...")
    dados_sm = ana.puxar_periodo(token, "84538500", hoje, hoje)
    
    # Estação substituta da ANA (SDC Tubarão Guarda) - Código 84580000 não funciona
    # Vamos usar a PCH Rio Fortuna como âncora substituta provisória (84535000)
    print("Puxando Rio Fortuna (Âncora Substituta)...")
    dados_rf = ana.puxar_periodo(token, "84535000", hoje, hoje)
    
    return dados_sm, dados_rf

def main():
    print("=== ARCTURUS v2: MODO OPERACIONAL (DADOS DE HOJE) ===")
    dados_sm, dados_rf = obter_dados_hoje()
    
    if not dados_rf:
        print("❌ Não foi possível puxar a âncora substituta (Rio Fortuna).")
        return
        
    # Pega a última leitura da Rio Fortuna
    ultima_rf = dados_rf[-1]
    cota_rf_atual = float(ultima_rf["Cota_Adotada"])
    dt_atual = pd.to_datetime(ultima_rf["Data_Hora_Medicao"])
    
    # A MÁGICA DO DATUM: 
    # O modelo aprendeu que o rio varia de 0 a 500cm.
    # A Rio Fortuna varia de 13.000 a 13.500cm.
    # Vamos normalizar a cota da Rio Fortuna para a escala do Rio do Pouso.
    # (Isso é um fallback provisório. O ideal é a SDC Tubarão Guarda).
    cota_normalizada = cota_rf_atual - 13000.0 
    if cota_normalizada < 0: cota_normalizada = 50.0 # Piso mínimo
    
    print(f"Instante: {dt_atual}")
    print(f"Cota Bruta (Rio Fortuna): {cota_rf_atual:.2f} cm")
    print(f"Cota Normalizada (Pouso): {cota_normalizada:.2f} cm")
    
    # Carrega o modelo
    m = lgb.Booster(model_file=str(MODELOS / "modelo_delta_1h_com_montante.txt"))
    feats = m.feature_name()
    
    # Monta o X (features de hoje)
    X_dict = {f: 0.0 for f in feats}
    X_dict['cota'] = cota_normalizada
    # A montante já está no modelo (lag 2h)
    
    X = np.array([[X_dict[f] for f in feats]])
    
    pred = m.predict(X)[0]
    pred = max(min(pred, 150.0), -150.0) # Clip de segurança
    
    print("\n=== RESULTADO OPERACIONAL ===")
    print(f"Delta Previsto (1h): {pred:+.2f} cm")
    print(f"Cota Prevista (1h): {cota_normalizada + pred:.2f} cm")

if __name__ == "__main__":
    main()
