import requests
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# Coordenadas da bacia (média dos 8 pontos)
LAT = -28.3
LON = -49.2

URL = "https://api.open-meteo.com/v1/forecast"

def baixar_previsao():
    print("Baixando previsão de chuva (Open-Meteo Forecast)...")
    params = {
        "latitude": LAT,
        "longitude": LON,
        "hourly": "precipitation",
        "forecast_days": 7,
        "timezone": "America/Sao_Paulo"
    }
    r = requests.get(URL, params=params, timeout=30)
    if r.status_code == 200:
        dados = r.json()
        h = dados.get("hourly", {})
        df = pd.DataFrame({
            "timestamp": h.get("time", []),
            "chuva_prevista_mm": h.get("precipitation", [])
        })
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df = df.set_index("timestamp")
        caminho = BASE / "data" / "previsao_chuva_bacia.csv"
        df.to_csv(caminho)
        print(f"✅ Salvo em: {caminho} ({len(df)} horas)")
        print(f"   Chuva total prevista: {df['chuva_prevista_mm'].sum():.1f} mm")
    else:
        print(f"❌ Erro HTTP: {r.status_code}")

if __name__ == "__main__":
    baixar_previsao()
