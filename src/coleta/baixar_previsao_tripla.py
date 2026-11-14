#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta previsão de chuva de TRÊS fontes (ECMWF + GFS + UKMO) via Open-Meteo."""

import requests
import pandas as pd
import json
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"

LAT, LON = -28.35, -49.30
MODELOS = "ecmwf_ifs025,gfs_global,ukmo_global_deterministic_10km"

URL = "https://api.open-meteo.com/v1/forecast"
params = {
    "latitude": LAT,
    "longitude": LON,
    "hourly": "precipitation",
    "models": MODELOS,
    "forecast_days": 3,
    "timezone": "America/Sao_Paulo",
}

print(f"Buscando previsão (ECMWF + GFS + UKMO) para {LAT}, {LON}...")
r = requests.get(URL, params=params, timeout=30)
r.raise_for_status()
dados = r.json()

df = pd.DataFrame({"timestamp": dados["hourly"]["time"]})
df["timestamp"] = pd.to_datetime(df["timestamp"])

for col in dados["hourly"]:
    if col.startswith("precipitation_"):
        modelo = col.replace("precipitation_", "")
        df[f"chuva_{modelo}_mm"] = dados["hourly"][col]

colunas_chuva = [c for c in df.columns if c.startswith("chuva_")]

# Totais por fonte (72h)
totais = {col: float(df[col].sum()) for col in colunas_chuva}

# Divergência total (no total de 72h): max(total) - min(total)
div_total = max(totais.values()) - min(totais.values())

# Divergência horária máxima (pior hora): max(divergencia_horaria)
df["div_horaria"] = df[colunas_chuva].max(axis=1) - df[colunas_chuva].min(axis=1)
div_horaria_max = float(df["div_horaria"].max())

# Média e pior caso (hora a hora)
df["chuva_media_mm"] = df[colunas_chuva].mean(axis=1)
df["chuva_pior_caso_mm"] = df[colunas_chuva].max(axis=1)
media = float(df["chuva_media_mm"].sum())
pior = float(df["chuva_pior_caso_mm"].sum())

# Confiança: baseada na divergência TOTAL (não na horária)
if div_total <= 10:
    confianca = "ALTA"
elif div_total <= 25:
    confianca = "MÉDIA"
else:
    confianca = "BAIXA"

# Salvar CSV
csv_path = DATA / "previsao_chuva_tripla.csv"
df.to_csv(csv_path, index=False)
print(f"[OK] CSV salvo: {csv_path} ({len(df)} horas)")

# Salvar JSON
payload = {
    "timestamp_coleta": datetime.now().isoformat(),
    "ecmwf_72h_mm": round(totais.get("chuva_ecmwf_ifs025_mm", 0), 1),
    "gfs_72h_mm": round(totais.get("chuva_gfs_global_mm", 0), 1),
    "ukmo_72h_mm": round(totais.get("chuva_ukmo_global_deterministic_10km_mm", 0), 1),
    "media_72h_mm": round(media, 1),
    "pior_caso_72h_mm": round(pior, 1),
    "divergencia_total_mm": round(div_total, 1),
    "divergencia_horaria_max_mm": round(div_horaria_max, 1),
    "confianca": confianca,
}
json_path = DATA / "chuva_ensemble_consolidada.json"
with open(json_path, "w") as f:
    json.dump(payload, f, indent=2)
print(f"[OK] JSON consolidado: {json_path}")
print(f"   ECMWF: {payload['ecmwf_72h_mm']:.1f} mm | GFS: {payload['gfs_72h_mm']:.1f} mm | UKMO: {payload['ukmo_72h_mm']:.1f} mm")
print(f"   Média: {payload['media_72h_mm']:.1f} mm | Pior: {payload['pior_caso_72h_mm']:.1f} mm")
print(f"   Divergência total: {payload['divergencia_total_mm']:.1f} mm | Horária máx: {payload['divergencia_horaria_max_mm']:.1f} mm")
print(f"   Confiança: {payload['confianca']}")
