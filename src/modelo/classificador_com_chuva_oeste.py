import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
import json
import requests
from datetime import datetime, timedelta

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar o modelo salvo
modelo = lgb.Booster(model_file=str(BASE / "modelos" / "classificador_extremos_final.txt"))
features_original = modelo.feature_name()
print(f"Features do modelo original: {len(features_original)}")

# 2. Carregar a cota atual (ERAB)
with open(BASE / "tubarao_saneamento_dados.json", "r") as f:
    dados = json.load(f)
cota_atual = dados.get("cota_cm", 64.0)
print(f"Cota atual (ERAB): {cota_atual:.1f} cm")

# 3. Carregar a chuva prevista da bacia (Open-Meteo)
prev = pd.read_csv(BASE / "data" / "previsao_chuva_bacia.csv", index_col=0, parse_dates=True)
prev = prev["chuva_prevista_mm"]
chuva_48h = prev.iloc[:48].sum()
print(f"Chuva prevista bacia (48h): {chuva_48h:.1f} mm")

# 4. Puxar a chuva do Oeste (Chapecó, Xanxerê, Joaçaba)
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
    params = {"latitude": lat, "longitude": lon, "start_date": ontem, "end_date": hoje,
              "hourly": "precipitation", "timezone": "America/Sao_Paulo"}
    try:
        r = requests.get(URL_ARCHIVE, params=params, timeout=60)
        if r.status_code == 200:
            h = r.json()["hourly"]
            s = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
            return s.sum()
    except Exception:
        pass
    return 0.0

def chuva_prevista_48h(lat, lon):
    params = {"latitude": lat, "longitude": lon, "hourly": "precipitation", "forecast_days": 2, "timezone": "America/Sao_Paulo"}
    try:
        r = requests.get(URL_FORECAST, params=params, timeout=60)
        if r.status_code == 200:
            h = r.json()["hourly"]
            s = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
            return s.sum()
    except Exception:
        pass
    return 0.0

total_obs_oeste = 0
total_prev_oeste = 0
for nome, (lat, lon) in PONTOS_OESTE.items():
    obs = chuva_observada_24h(lat, lon)
    prev = chuva_prevista_48h(lat, lon)
    total_obs_oeste += obs
    total_prev_oeste += prev
    print(f"{nome}: obs 24h = {obs:.1f} mm | prev 48h = {prev:.1f} mm")

print(f"Total Oeste: obs = {total_obs_oeste:.1f} mm | prev = {total_prev_oeste:.1f} mm")

# 5. Montar o X para o modelo (apenas com as features originais)
# (O modelo original não foi treinado com a chuva do Oeste, então não podemos adicionar como feature)
# MAS podemos usar a chuva do Oeste como um "sinal de contexto" para o alerta
X_hoje = {
    "cota": cota_atual,
    "d1": 0.0, "d3": 0.0, "max3": cota_atual,
    "sin": np.sin(2 * np.pi * 297 / 365.25),
    "cos": np.cos(2 * np.pi * 297 / 365.25),
    "chuva_1d": 0.0, "chuva_2d": chuva_48h, "chuva_3d": chuva_48h,
    "chuva_5d": chuva_48h, "chuva_10d": chuva_48h, "chuva_30d": chuva_48h,
    "chuva_max_ponto_2d": chuva_48h,
}
X_pred = pd.DataFrame([X_hoje])[features_original]
prob = modelo.predict(X_pred)[0]
print(f"\nProbabilidade de cheia (modelo original): {prob:.2%}")

# 6. Ajuste manual baseado na chuva do Oeste (regra empírica)
# Se a chuva do Oeste for > 100 mm, a probabilidade sobe (porque a água vai descer)
if total_obs_oeste + total_prev_oeste > 300:
    prob_ajustada = min(prob + 0.15, 1.0)  # Aumenta 15%
    print(f"🚨 ALERTA: Chuva no Oeste > 300 mm. Probabilidade ajustada: {prob_ajustada:.2%}")
    print("   A água vai descer para a bacia do Tubarão em 24-48h.")
elif total_obs_oeste + total_prev_oeste > 150:
    prob_ajustada = min(prob + 0.05, 1.0)  # Aumenta 5%
    print(f"⚠️ ATENÇÃO: Chuva no Oeste > 150 mm. Probabilidade ajustada: {prob_ajustada:.2%}")
else:
    prob_ajustada = prob
    print(f"✅ Chuva no Oeste dentro do normal. Probabilidade: {prob_ajustada:.2%}")
