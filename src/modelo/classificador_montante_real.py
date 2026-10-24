import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
import json
import requests
from datetime import datetime, timedelta
import warnings

warnings.filterwarnings("ignore")

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar o modelo salvo
modelo = lgb.Booster(model_file=str(BASE / "modelos" / "classificador_extremos_final.txt"))
features_original = modelo.feature_name()
print(f"Features do modelo original: {len(features_original)}")

# 2. Carregar a cota atual (ERAB)
try:
    with open(BASE / "tubarao_saneamento_dados.json", "r") as f:
        dados = json.load(f)
    cota_atual = dados.get("cota_cm", 64.0)
except FileNotFoundError:
    cota_atual = 64.0
print(f"Cota atual (ERAB): {cota_atual:.1f} cm")

# 3. Carregar a chuva prevista da bacia (Open-Meteo)
try:
    prev_bacia = pd.read_csv(BASE / "data" / "previsao_chuva_bacia.csv", index_col=0, parse_dates=True)
    chuva_48h = prev_bacia["chuva_prevista_mm"].iloc[:48].sum()
except FileNotFoundError:
    chuva_48h = 0.0
print(f"Chuva prevista bacia (48h): {chuva_48h:.1f} mm\n")

# 4. Puxar a chuva na VERDADEIRA montante da Bacia do Tubarão
PONTOS_MONTANTE = {
    "orleans": (-28.358, -49.289),
    "rio_fortuna": (-28.132, -49.116),
    "bom_jardim_da_serra": (-28.335, -49.594),
    "lauro_muller": (-28.393, -49.395),
}

URL_ARCHIVE = "https://archive-api.open-meteo.com/v1/archive"
URL_FORECAST = "https://api.open-meteo.com/v1/forecast"

def chuva_observada_24h(lat, lon):
    hoje = datetime.now().strftime("%Y-%m-%d")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
    params = {"latitude": lat, "longitude": lon, "start_date": ontem, "end_date": hoje,
              "hourly": "precipitation", "timezone": "America/Sao_Paulo"}
    try:
        r = requests.get(URL_ARCHIVE, params=params, timeout=10)
        if r.status_code == 200:
            h = r.json().get("hourly", {})
            if "precipitation" in h and "time" in h:
                s = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
                # Pega as últimas 24h exatas a partir de agora
                agora = pd.Timestamp.now(tz="America/Sao_Paulo").tz_localize(None)
                s = s[(s.index >= agora - timedelta(hours=24)) & (s.index <= agora)]
                return s.sum()
    except Exception:
        pass
    return 0.0

def chuva_prevista_48h(lat, lon):
    params = {"latitude": lat, "longitude": lon, "hourly": "precipitation", "forecast_days": 2, "timezone": "America/Sao_Paulo"}
    try:
        r = requests.get(URL_FORECAST, params=params, timeout=10)
        if r.status_code == 200:
            h = r.json().get("hourly", {})
            if "precipitation" in h and "time" in h:
                s = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
                return s.iloc[:48].sum()
    except Exception:
        pass
    return 0.0

print("=== CHUVA NA MONTANTE DA BACIA DO TUBARÃO ===")
total_obs = 0
total_prev = 0
for nome, (lat, lon) in PONTOS_MONTANTE.items():
    obs = chuva_observada_24h(lat, lon)
    prev = chuva_prevista_48h(lat, lon)
    total_obs += obs
    total_prev += prev
    print(f"{nome.upper()}: obs 24h = {obs:.1f} mm | prev 48h = {prev:.1f} mm")

print(f"\nTotal Montante: obs = {total_obs:.1f} mm | prev = {total_prev:.1f} mm")

# 5. Montar o X para o modelo
X_hoje = {
    "cota": cota_atual,
    "d1": 0.0, "d3": 0.0, "max3": cota_atual,
    "sin": np.sin(2 * np.pi * 297 / 365.25),
    "cos": np.cos(2 * np.pi * 297 / 365.25),
    "chuva_1d": 0.0, "chuva_2d": chuva_48h, "chuva_3d": chuva_48h,
    "chuva_5d": chuva_48h, "chuva_10d": chuva_48h, "chuva_30d": chuva_48h,
    "chuva_max_ponto_2d": chuva_48h,
}

# Preenche features ausentes no dummy dictionary com 0.0 para evitar erro de shape
for col in features_original:
    if col not in X_hoje:
        X_hoje[col] = 0.0

X_pred = pd.DataFrame([X_hoje])[features_original]
prob = modelo.predict(X_pred)[0]
print(f"\nProbabilidade de cheia (modelo original): {prob:.2%}")

# 6. Ajuste baseado na chuva da montante real
if total_obs + total_prev > 200:
    prob_ajustada = min(prob + 0.20, 1.0)
    print(f"🚨 ALERTA: Chuva na montante > 200 mm. Probabilidade ajustada: {prob_ajustada:.2%}")
    print("   A água já está descendo a serra em direção a São Ludgero e Tubarão.")
elif total_obs + total_prev > 100:
    prob_ajustada = min(prob + 0.08, 1.0)
    print(f"⚠️ ATENÇÃO: Chuva na montante > 100 mm. Probabilidade ajustada: {prob_ajustada:.2%}")
else:
    prob_ajustada = prob
    print(f"✅ Chuva na montante dentro do normal. Probabilidade: {prob_ajustada:.2%}")
