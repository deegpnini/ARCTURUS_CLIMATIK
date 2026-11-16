#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta previsão do tempo (diária) para as cidades da bacia do Rio Tubarão."""

import requests
import json
import os
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
DATA = BASE / "data"

PONTOS = {
    # Cabeceira
    "lauro_muller": (-28.39, -49.39),
    "orleans": (-28.35, -49.30),
    "anitapolis": (-27.90, -49.13),
    "sao_bonifacio": (-27.90, -48.93),
    "grao_para": (-28.18, -49.22),
    "rio_fortuna": (-28.13, -49.10),
    "santa_rosa_de_lima": (-28.03, -49.13),
    # Médio Curso
    "braco_do_norte": (-28.27, -49.17),
    "sao_ludgero": (-28.32, -49.20),
    "pedras_grandes": (-28.43, -49.18),
    "armazem": (-28.26, -49.02),
    "gravatal": (-28.33, -49.05),
    "sao_martinho": (-28.16, -48.98),
    # Foz / Litoral
    "tubarao": (-28.48, -49.02),
    "capivari_de_baixo": (-28.45, -48.98),
    "treze_de_maio": (-28.55, -49.15),
    "jaguaruna": (-28.61, -49.03),
    "sangao": (-28.63, -49.13),
    "laguna": (-28.48, -48.78),
}

URL = "https://api.open-meteo.com/v1/forecast"
resultado = {}

for nome, (lat, lon) in PONTOS.items():
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_sum",
        "forecast_days": 3,
        "timezone": "America/Sao_Paulo",
    }
    try:
        r = requests.get(URL, params=params, timeout=20)
        r.raise_for_status()
        dados = r.json()
        daily = dados["daily"]
        
        dias = {}
        for i in range(3):
            data = daily["time"][i]
            dias[data] = {
                "data": data,
                "temp_max": daily["temperature_2m_max"][i],
                "temp_min": daily["temperature_2m_min"][i],
                "chuva": daily["precipitation_sum"][i],
            }
        
        resultado[nome] = {
            "hoje": dias[daily["time"][0]],
            "amanha": dias[daily["time"][1]],
            "depois_amanha": dias[daily["time"][2]],
        }
        print(f"[OK] {nome}")
    except Exception as e:
        print(f"[ERRO] {nome}: {e}")

json_path = DATA / "previsao_tempo.json"
tmp_path = json_path.with_suffix(".json.tmp")
with open(tmp_path, "w", encoding="utf-8") as f:
    json.dump(resultado, f, indent=2, ensure_ascii=False)
os.replace(tmp_path, json_path)

meta_path = DATA / "previsao_tempo_meta.json"
meta_tmp = meta_path.with_suffix(".json.tmp")
with open(meta_tmp, "w", encoding="utf-8") as f:
    json.dump(
        {
            "consulta_em": datetime.now().astimezone().isoformat(timespec="minutes"),
            "provedor": "Open-Meteo Forecast API",
            "modelo_solicitado": "best_match",
            "rodada_modelo": None,
            "observacao": "A API consultada não expõe o horário de inicialização da rodada.",
        },
        f,
        indent=2,
        ensure_ascii=False,
    )
os.replace(meta_tmp, meta_path)
print(f"\n[OK] Previsão salva: {json_path} ({len(resultado)} cidades)")
print(f"Consulta realizada em: {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %z')}")
print("Rodada de inicialização do modelo: não fornecida pela API.")
