import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta
import time

BASE = Path(__file__).resolve().parents[2]

PONTOS_OESTE = {
    "chapeco": (-27.100, -52.615),
    "xanxere": (-26.875, -52.405),
    "joacaba": (-27.175, -51.505),
}

URL_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
URL_FORECAST = "https://api.open-meteo.com/v1/forecast"

def chuva_observada_24h(lat, lon):
    hoje = datetime.now().strftime("%Y-%m-%d")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    params = {
        "latitude": lat, "longitude": lon,
        "start_date": ontem, "end_date": hoje,
        "hourly": "precipitation", "timezone": "America/Sao_Paulo"
    }
    try:
        r = requests.get(URL_ARCHIVE, params=params, timeout=60)
        if r.status_code == 200:
            h = r.json()["hourly"]
            s = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
            return s.sum()
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar observada: {e}")
    return 0.0

def chuva_prevista_48h(lat, lon):
    params = {
        "latitude": lat, "longitude": lon,
        "hourly": "precipitation", "forecast_days": 2,
        "timezone": "America/Sao_Paulo"
    }
    try:
        r = requests.get(URL_FORECAST, params=params, timeout=60)
        if r.status_code == 200:
            h = r.json()["hourly"]
            s = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
            return s.sum()
    except Exception as e:
        print(f"  ⚠️ Erro ao buscar prevista: {e}")
    return 0.0

print("=== CHUVA NO OESTE DE SC (MONTANTE DISTANTE) ===")
total_obs = 0
total_prev = 0
for nome, (lat, lon) in PONTOS_OESTE.items():
    obs = chuva_observada_24h(lat, lon)
    time.sleep(2)
    prev = chuva_prevista_48h(lat, lon)
    time.sleep(2)
    total_obs += obs
    total_prev += prev
    print(f"{nome}: observada 24h = {obs:.1f} mm | prevista 48h = {prev:.1f} mm")

print(f"\nTotal Oeste: observada = {total_obs:.1f} mm | prevista = {total_prev:.1f} mm")
if total_obs + total_prev > 100:
    print("🚨 ALERTA: Chuva significativa no Oeste. A água vai descer para a bacia do Tubarão.")
else:
    print("✅ Chuva no Oeste dentro do normal.")
