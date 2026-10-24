import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

def get_session():
    s = requests.Session()
    retries = Retry(total=2, backoff_factor=1, status_forcelist=[502, 503, 504])
    s.mount("http://", HTTPAdapter(max_retries=retries))
    s.mount("https://", HTTPAdapter(max_retries=retries))
    return s

def coletar_cemaden_seguro(uf="SC", tipo=1, timeout=8):
    urls = [
        f"http://150.163.255.240/CEMADEN/resources/parceiros/{uf}/{tipo}",
    ]
    session = get_session()
    for url in urls:
        try:
            r = session.get(url, timeout=timeout)
            if r.status_code == 200:
                return r.json()
        except Exception:
            continue
    return None

def main():
    print("Tentando CEMADEN (SC - Pluviométrica)...")
    dados = coletar_cemaden_seguro()
    
    if dados is None:
        print("⚠️ CEMADEN indisponível (timeout).")
        print("   Fallback: usando chuva da Open-Meteo (já salva em data/chuva_bacia_openmeteo.csv).")
        print("   O pipeline continua sem quebrar.")
        return
    
    estacoes = dados.get("cemaden", [])
    print(f"Total de estações: {len(estacoes)}")
    
    estacoes_tubarao = [
        e for e in estacoes
        if -28.7 <= float(e.get("latitude", 0)) <= -28.0
        and -49.5 <= float(e.get("longitude", 0)) <= -48.8
    ]
    
    print(f"Estações na bacia do Tubarão: {len(estacoes_tubarao)}")
    for e in estacoes_tubarao:
        print(f"  {e.get('nome')} | Chuva: {e.get('chuva')} mm | Nível: {e.get('nivel')} | {e.get('datahora')}")
    
    if estacoes_tubarao:
        df = pd.DataFrame(estacoes_tubarao)
        caminho = BASE / "data" / "cemaden_sc_tubarao.csv"
        df.to_csv(caminho, index=False)
        print(f"✅ Salvo em: {caminho}")

if __name__ == "__main__":
    main()
