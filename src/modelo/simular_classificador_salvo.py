import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
import json

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar o modelo salvo
caminho_modelo = BASE / "modelos" / "classificador_extremos_final.txt"
if not caminho_modelo.exists():
    print("❌ Modelo não encontrado. Rode treinar_classificador_extremos_final.py primeiro.")
    exit()

modelo = lgb.Booster(model_file=str(caminho_modelo))
features = modelo.feature_name()
print(f"Modelo carregado: {len(features)} features")

# 2. Carregar a cota atual (Tubarão Saneamento)
json_cota = BASE / "tubarao_saneamento_dados.json"
if json_cota.exists():
    with open(json_cota, "r") as f:
        dados = json.load(f)
    cota_atual = dados.get("cota_cm", 67.0)
    print(f"Cota atual (ERAB): {cota_atual:.1f} cm")
else:
    cota_atual = 67.0
    print("⚠️ Cota não encontrada. Usando fallback de 67 cm.")

# 3. Carregar a previsão de chuva (Open-Meteo)
caminho_previsao = BASE / "data" / "previsao_chuva_bacia.csv"
if caminho_previsao.exists():
    prev = pd.read_csv(caminho_previsao, index_col=0, parse_dates=True)
    prev = prev["chuva_prevista_mm"]
    chuva_48h = prev.iloc[:48].sum()
    print(f"Chuva prevista (48h): {chuva_48h:.1f} mm")
else:
    chuva_48h = 0.0
    print("⚠️ Previsão de chuva não encontrada. Usando fallback de 0 mm.")

# 4. Carregar a cota do dia anterior (para o delta)
# (Usando um valor fictício, porque não temos o histórico diário da ERAB)
cota_ontem = cota_atual  # Assumindo que não mudou
delta_1d = cota_atual - cota_ontem

# 5. Montar o X para o dia de hoje
X_hoje = {
    "cota": cota_atual,
    "d1": delta_1d,
    "d3": delta_1d,
    "max3": cota_atual,
    "sin": np.sin(2 * np.pi * 297 / 365.25),
    "cos": np.cos(2 * np.pi * 297 / 365.25),
    "chuva_1d": 0.0,
    "chuva_2d": chuva_48h,
    "chuva_3d": chuva_48h,
    "chuva_5d": chuva_48h,
    "chuva_10d": chuva_48h,
    "chuva_30d": chuva_48h,
    "chuva_max_ponto_2d": chuva_48h,  # Aproximação
}

# 6. Prever
X_pred = pd.DataFrame([X_hoje])[features]
prob = modelo.predict(X_pred)[0]
print(f"\n=== SIMULAÇÃO DE ALERTA (24/10/2026) ===")
print(f"Cota atual: {cota_atual:.1f} cm")
print(f"Chuva prevista (48h): {chuva_48h:.1f} mm")
print(f"Probabilidade de cheia (>= 300 cm): {prob:.2%}")
if prob > 0.1:
    print("🚨 ALERTA: Probabilidade de cheia elevada!")
else:
    print("✅ Sem sinal de cheia iminente.")
