#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta previsão de chuva de DUAS fontes (ECMWF + GFS) via Open-Meteo."""

import requests
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"

# Coordenadas da cabeceira (Orleans, Lauro Müller)
LAT, LON = -28.35, -49.30

# Modelos: ECMWF IFS (europeu) e GFS (americano)
MODELOS = "ecmwf_ifs025,gfs_global"

URL = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT,
    "longitude": LON,
    "hourly": "precipitation",
    "models": MODELOS,
    "forecast_days": 3,  # 72 horas
    "timezone": "America/Sao_Paulo",
}

print(f"Buscando previsão (ECMWF + GFS) para {LAT}, {LON}...")
r = requests.get(URL, params=params, timeout=30)
r.raise_for_status()
dados = r.json()

# Extrair as séries
df = pd.DataFrame({"timestamp": dados["hourly"]["time"]})
df["timestamp"] = pd.to_datetime(df["timestamp"])

# As chaves vêm como 'precipitation_ecmwf_ifs025' e 'precipitation_gfs_global'
for col in dados["hourly"]:
    if col.startswith("precipitation_"):
        modelo = col.replace("precipitation_", "")
        df[f"chuva_{modelo}_mm"] = dados["hourly"][col]

# Calcular divergência (média das duas fontes)
colunas_chuva = [c for c in df.columns if c.startswith("chuva_")]
df["chuva_media_mm"] = df[colunas_chuva].mean(axis=1)
df["divergencia_mm"] = df[colunas_chuva].max(axis=1) - df[colunas_chuva].min(axis=1)

# Salvar CSV detalhado
csv_path = DATA / "previsao_chuva_dupla.csv"
df.to_csv(csv_path, index=False)
print(f"[OK] CSV salvo: {csv_path} ({len(df)} horas)")

# Salvar JSON consolidado (para o boletim e o motor)
total_ecmwf = float(df["chuva_ecmwf_ifs025_mm"].sum()) if "chuva_ecmwf_ifs025_mm" in df else 0
total_gfs = float(df["chuva_gfs_global_mm"].sum()) if "chuva_gfs_global_mm" in df else 0
media = (total_ecmwf + total_gfs) / 2
pior = max(total_ecmwf, total_gfs)
div = abs(total_ecmwf - total_gfs)

payload = {
    "timestamp_coleta": datetime.now().isoformat(),
    "ecmwf_72h_mm": round(total_ecmwf, 1),
    "gfs_72h_mm": round(total_gfs, 1),
    "media_72h_mm": round(media, 1),
    "pior_caso_72h_mm": round(pior, 1),
    "divergencia_mm": round(div, 1),
    "confianca": "ALTA" if div <= 10 else ("MÉDIA" if div <= 25 else "BAIXA"),
}
json_path = DATA / "chuva_ensemble_consolidada.json"
with open(json_path, "w") as f:
    json.dump(payload, f, indent=2)
print(f"[OK] JSON consolidado: {json_path}")
print(f"   ECMWF: {total_ecmwf:.1f} mm | GFS: {total_gfs:.1f} mm | Δ: {div:.1f} mm")
