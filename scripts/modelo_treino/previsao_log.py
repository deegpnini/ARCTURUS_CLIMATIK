#!/usr/bin/env python3
"""
ARCTURUS_FORECAST — modo operacional
Registra cada previsao para auditoria futura.
"""
import json, os, sys, subprocess, pickle
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
LOG = f"{CACHE}/previsoes_log.jsonl"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

# Modelo treinado (precisa baixar do Drive o .pkl)
MODELO_PATH = f"{CACHE}/modelo_delta_1h.pkl"
MODELO_VERSION = "v1.0"

def prever(codigo, horizonte):
    """Faz previsao e registra no log."""
    # Le ultima cota
    import urllib.request
    token = get_token()
    url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
           f"?Codigos_Estacoes={codigo}"
           f"&Tipo%20Filtro%20Data=DATA_LEITURA"
           f"&Range%20Intervalo%20de%20busca=DIAS_2")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode('utf-8'))
    
    items = d.get('items', [])
    if not items:
        return None
    
    items.sort(key=lambda x: x.get('Data_Hora_Medicao', ''))
    ultima = items[-1]
    cota_atual = ultima.get('Cota_Adotada')
    
    # Registra no log
    entrada = {
        'timestamp': datetime.now().isoformat(),
        'codigo': codigo,
        'horizonte': horizonte,
        'cota_atual': cota_atual,
        'data_medicao': ultima.get('Data_Hora_Medicao'),
        'modelo_version': MODELO_VERSION,
        'features_disponiveis': 0,  # TODO
        'previsao': None,  # TODO: usar modelo
    }
    
    with open(LOG, 'a') as f:
        f.write(json.dumps(entrada, default=str) + '\n')
    
    return entrada

if __name__ == "__main__":
    print("Modo operacional ARCTURUS_FORECAST")
    print("Log:", LOG)
    print()
    print("ATENCAO: este script precisa do modelo .pkl para funcionar")
    print("-> exportar do Colab: modelo_delta_1h.pkl")
    print()
    r = prever("84580000", "1h")
    print(r)
