import requests
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# Coordenadas do Rio do Pouso (84580000)
LAT = -28.4206
LON = -49.1064

URL = "https://flood-api.open-meteo.com/v1/flood"

def coletar_flood():
    print(f"Consultando Open-Meteo Flood (GloFAS) para ({LAT}, {LON})...")
    params = {
        "latitude": LAT,
        "longitude": LON,
        "daily": "river_discharge",
        "forecast_days": 7
    }
    try:
        r = requests.get(URL, params=params, timeout=30)
        if r.status_code == 200:
            dados = r.json()
            print("Resposta recebida:")
            print(f"  Unidade: {dados.get('daily_units', {}).get('river_discharge', 'N/A')}")
            print(f"  Datas: {dados.get('daily', {}).get('time', [])}")
            print(f"  Vazão: {dados.get('daily', {}).get('river_discharge', [])}")
            
            # Salvar em CSV
            df = pd.DataFrame({
                "data": dados.get("daily", {}).get("time", []),
                "vazao_m3s": dados.get("daily", {}).get("river_discharge", [])
            })
            caminho = BASE / "data" / "flood_openmeteo_tubarao.csv"
            df.to_csv(caminho, index=False)
            print(f"✅ Salvo em: {caminho}")
        else:
            print(f"❌ Erro HTTP: {r.status_code}")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    coletar_flood()
