import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
import warnings

warnings.filterwarnings("ignore")

BASE = Path.cwd()

# 1. Carregar Modelo de Classificação
MODEL_PATH = BASE / "modelos" / "classificador_extremos_final.txt"
if not MODEL_PATH.exists():
    print(f"❌ Erro: Modelo não encontrado em {MODEL_PATH}")
    exit(1)

modelo = lgb.Booster(model_file=str(MODEL_PATH))
features_original = modelo.feature_name()

# 2. Carregar Cota Atual (ERAB / Tubarão Saneamento)
COTA_PATH = BASE / "tubarao_saneamento_dados.json"
cota_atual = 64.0
if COTA_PATH.exists():
    try:
        with open(COTA_PATH, "r") as f:
            dados_cota = json.load(f)
        cota_atual = float(dados_cota.get("cota_cm", 64.0))
    except Exception:
        pass

# 3. Carregar Ensemble de Chuva
ENSEMBLE_PATH = BASE / "data" / "chuva_ensemble_consolidada.json"
if not ENSEMBLE_PATH.exists():
    print(f"❌ Erro: Ensemble de chuva não encontrado em {ENSEMBLE_PATH}")
    exit(1)

with open(ENSEMBLE_PATH, "r") as f:
    ens = json.load(f)

pior_caso_48h = ens.get("pior_caso_48h_mm", 0.0)
media_48h = ens.get("media_48h_mm", 0.0)
ecmwf_48h = ens.get("ecmwf_48h_mm", 0.0)
diferenca_mm = ens.get("diferenca_mm", 0.0)
incerteza_alta = ens.get("incerteza_alta", False)

def montar_features(cota, chuva_48h):
    d = {
        "cota": cota,
        "d1": 0.0, "d3": 0.0, "max3": cota,
        "sin": np.sin(2 * np.pi * 297 / 365.25),
        "cos": np.cos(2 * np.pi * 297 / 365.25),
        "chuva_1d": chuva_48h / 2.0,
        "chuva_2d": chuva_48h,
        "chuva_3d": chuva_48h,
        "chuva_5d": chuva_48h,
        "chuva_10d": chuva_48h,
        "chuva_30d": chuva_48h,
        "chuva_max_ponto_2d": chuva_48h,
    }
    for col in features_original:
        if col not in d:
            d[col] = 0.0
    return pd.DataFrame([d])[features_original]

# Predict Pior Caso
df_pior = montar_features(cota_atual, pior_caso_48h)
prob_pior = float(modelo.predict(df_pior)[0])

# Predict Média
df_media = montar_features(cota_atual, media_48h)
prob_media = float(modelo.predict(df_media)[0])

# Predict Cenário Otimista (ECMWF)
df_ecmwf = montar_features(cota_atual, ecmwf_48h)
prob_ecmwf = float(modelo.predict(df_ecmwf)[0])

print("=== ARCTURUS CLIMATIK: SIMULAÇÃO DE PROBABILIDADE POR ENSEMBLE ===")
print(f"📍 Cota Atual Lida: {cota_atual:.1f} cm")
print(f"📊 Amplitude de Incerteza da Chuva: Δ = {diferenca_mm:.1f} mm\n")

print(f"1. Cenário Otimista (ECMWF IFS - {ecmwf_48h:.1f} mm):")
print(f"   └─ Probabilidade de Cheia (>300cm): {prob_ecmwf:.2%}")

print(f"\n2. Cenário Médio (Consenso - {media_48h:.1f} mm):")
print(f"   └─ Probabilidade de Cheia (>300cm): {prob_media:.2%}")

print(f"\n3. Cenário Conservador (Pior Caso / Open-Meteo - {pior_caso_48h:.1f} mm):")
print(f"   └─ Probabilidade de Cheia (>300cm): {prob_pior:.2%}")

# Salva resultado da simulação para consumo do painel
payload_simulacao = {
    "cota_atual_cm": cota_atual,
    "prob_ecmwf": round(prob_ecmwf * 100, 2),
    "prob_media": round(prob_media * 100, 2),
    "prob_pior_caso": round(prob_pior * 100, 2),
    "delta_prob_pct": round(abs(prob_pior - prob_ecmwf) * 100, 2),
    "incerteza_critica": incerteza_alta
}

with open(BASE / "data" / "simulacao_probabilidade_atual.json", "w", encoding="utf-8") as f:
    json.dump(payload_simulacao, f, indent=4)

print(f"\n[OK] Simulação de probabilidade gravada em: data/simulacao_probabilidade_atual.json")
