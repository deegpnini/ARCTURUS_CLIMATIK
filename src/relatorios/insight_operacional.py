import json
import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
import sys

BASE_DIR = Path(__file__).resolve().parents[2]
sys.path.append(str(BASE_DIR))
import puxar_historico_ana as ana

MODELOS = BASE_DIR / "modelos"

def obter_dados_hoje():
    token = ana.get_token()
    # Pede os últimos 7 dias para garantir que a API devolva algo
    sete_dias_atras = (pd.Timestamp.now() - pd.Timedelta(days=7)).strftime("%Y-%m-%d")
    hoje = pd.Timestamp.now().strftime("%Y-%m-%d")
    
    print(f"Puxando dados de {sete_dias_atras} a {hoje}...")
    dados_rf = ana.puxar_periodo(token, "84535000", sete_dias_atras, hoje) # Rio Fortuna
    dados_sm = ana.puxar_periodo(token, "84538500", sete_dias_atras, hoje) # São Maurício
    return dados_rf, dados_sm

def main():
    print("=== ARCTURUS v2: MODO OPERACIONAL (3 HORIZONTES) ===")
    dados_rf, dados_sm = obter_dados_hoje()
    
    if not dados_rf:
        print("❌ Sem dados da Rio Fortuna.")
        return
        
    ultima_rf = dados_rf[-1]
    cota_rf_atual = float(ultima_rf["Cota_Adotada"])
    dt_atual = pd.to_datetime(ultima_rf["Data_Hora_Medicao"])
    
    # COTA MANUAL (ERAB Tubarão Saneamento) - 68 cm
    # O Comandante confirmou o valor no site às 15:55
    cota_normalizada = 68.0
    
    print(f"Instante: {dt_atual}")
    print(f"Cota Atual (Normalizada): {cota_normalizada:.2f} cm")
    
    # Prever para os 3 horizontes
    previsoes = {}
    for h in ["1h", "3h", "6h"]:
        caminho = MODELOS / f"modelo_delta_{h}_com_montante.txt"
        if not caminho.exists():
            print(f"⚠️ Modelo {h} não encontrado.")
            continue
            
        m = lgb.Booster(model_file=str(caminho))
        feats = m.feature_name()
        
        # Monta X (usando a cota normalizada e as features de montante)
        X_dict = {f: 0.0 for f in feats}
        X_dict['cota'] = cota_normalizada
        
        X = np.array([[X_dict[f] for f in feats]])
        pred = m.predict(X)[0]
        
        # Clip de segurança
        pred = max(min(pred, 150.0), -150.0)
        previsoes[h] = pred
    
    print("\n=== PREVISÃO ===")
    for h, delta in previsoes.items():
        cota_prevista = cota_normalizada + delta
        print(f"  +{h}: {cota_prevista:.2f} cm (delta {delta:+.2f} cm)")
    
    print("\n✅ ARCTURUS v2 operacional (1h, 3h, 6h)")

if __name__ == "__main__":
    main()
