
import pandas as pd
import numpy as np
import joblib

# Carregar modelo
modelo = joblib.load('arcturus_v1_0_final.pkl')
features = ['profundidade_km', 'latitude', 'longitude', 'proximidade_falha']

def prever_risco(novo_evento):
    """Recebe um dicionario com as features e retorna a classe e probabilidades."""
    df = pd.DataFrame([novo_evento])
    X = df[features].values
    probas = modelo.predict_proba(X)[0]
    classe = modelo.predict(X)[0]
    
    classes = {0: 'BAIXO', 1: 'MEDIO', 2: 'ALTO'}
    
    return {
        'classe': classes[classe],
        'probabilidade': {
            'BAIXO': probas[0],
            'MEDIO': probas[1],
            'ALTO': probas[2]
        },
        'alerta': probas[2] > 0.50  # threshold padrao
    }

# Exemplo de uso
if __name__ == '__main__':
    evento = {
        'profundidade_km': 45.0,
        'latitude': -20.5,
        'longitude': -70.0,
        'proximidade_falha': 120.0
    }
    resultado = prever_risco(evento)
    print("Resultado:", resultado)
