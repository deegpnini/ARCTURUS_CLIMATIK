#!/usr/bin/env python3
"""
coletar_mare_laguna.py — Coleta nível do mar (MSL) e vento costeiro na Barra de Laguna
(-28.48, -48.78) para monitorar a condição de contorno de jusante (remanso lagunar)
da Bacia do Rio Tubarão (ref.: Truccolo 1998; Melo 2018; IPH/UFRGS).
"""

import json
import math
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg2
import requests

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

LAT_LAGUNA = -28.48
LON_LAGUNA = -48.78
TZ = ZoneInfo("America/Sao_Paulo")


def calcular_componente_sul(vento_kmh: float, dir_graus: float) -> float:
    """
    Projeta a velocidade do vento sobre o eixo de empilhamento costeiro S/SSE (160°).
    Valores positivos indicam vento soprando de S/SE empurrando água contra a barra.
    """
    rad = math.radians(dir_graus - 160.0)
    return round(max(0.0, vento_kmh * math.cos(rad)), 2)


def classificar_remanso(mare_m: float, comp_sul_kmh: float) -> str:
    if mare_m >= 0.65 and comp_sul_kmh >= 28.0:
        return "ALTO_REMANSO"
    if mare_m >= 0.45 or comp_sul_kmh >= 20.0:
        return "ATENCAO_REMANSO"
    return "NORMAL"


def coletar() -> None:
    params_base = {
        "latitude": LAT_LAGUNA,
        "longitude": LON_LAGUNA,
        "timezone": "America/Sao_Paulo",
        "past_days": 1,
        "forecast_days": 2,
    }

    r_mar = requests.get(
        "https://marine-api.open-meteo.com/v1/marine",
        params={**params_base, "hourly": "sea_level_height_msl"},
        timeout=20,
    )
    r_mar.raise_for_status()
    h_mar = r_mar.json().get("hourly", {})
    mapa_mar = dict(zip(h_mar.get("time", []), h_mar.get("sea_level_height_msl", [])))

    r_vnt = requests.get(
        "https://api.open-meteo.com/v1/forecast",
        params={**params_base, "hourly": "wind_speed_10m,wind_direction_10m"},
        timeout=20,
    )
    r_vnt.raise_for_status()
    h_vnt = r_vnt.json().get("hourly", {})
    tempos = h_vnt.get("time", [])
    vel_list = h_vnt.get("wind_speed_10m", [])
    dir_list = h_vnt.get("wind_direction_10m", [])

    registros = []
    for ts_str, vel, direc in zip(tempos, vel_list, dir_list):
        mare = mapa_mar.get(ts_str)
        if mare is None or vel is None or direc is None:
            continue
        comp_sul = calcular_componente_sul(float(vel), float(direc))
        risco = classificar_remanso(float(mare), comp_sul)
        registros.append({
            "timestamp": ts_str,
            "mare_msl_m": round(float(mare), 3),
            "vento_kmh": round(float(vel), 1),
            "vento_dir_graus": round(float(direc), 1),
            "componente_sul_kmh": comp_sul,
            "risco_remanso": risco,
        })

    if not registros:
        raise RuntimeError("Nenhum registro horário válido retornado para Laguna.")

    conn = psycopg2.connect("postgresql:///arcturus")
    cur = conn.cursor()
    for reg in registros:
        cur.execute(
            """
            INSERT INTO contorno_jusante (
                timestamp, mare_msl_m, vento_kmh, vento_dir_graus,
                componente_sul_kmh, risco_remanso, fonte
            )
            VALUES (%s, %s, %s, %s, %s, %s, 'open-meteo-marine+weather')
            ON CONFLICT (timestamp) DO UPDATE SET
                mare_msl_m = EXCLUDED.mare_msl_m,
                vento_kmh = EXCLUDED.vento_kmh,
                vento_dir_graus = EXCLUDED.vento_dir_graus,
                componente_sul_kmh = EXCLUDED.componente_sul_kmh,
                risco_remanso = EXCLUDED.risco_remanso,
                criado_em = NOW();
            """,
            (
                reg["timestamp"],
                reg["mare_msl_m"],
                reg["vento_kmh"],
                reg["vento_dir_graus"],
                reg["componente_sul_kmh"],
                reg["risco_remanso"],
            ),
        )
    conn.commit()
    cur.close()
    conn.close()

    agora_hora = datetime.now(TZ).strftime("%Y-%m-%dT%H:00")
    atual = next((r for r in registros if r["timestamp"] == agora_hora), registros[len(registros) // 2])
    futuros_24h = [r for r in registros if r["timestamp"] >= agora_hora][:24]
    pico_mare_24h = max(futuros_24h, key=lambda x: x["mare_msl_m"]) if futuros_24h else atual
    pico_sul_24h = max(futuros_24h, key=lambda x: x["componente_sul_kmh"]) if futuros_24h else atual

    resumo = {
        "timestamp_consulta": datetime.now(TZ).isoformat(),
        "estacao_referencia": "Barra de Laguna / Lagoa de Santo Antônio (-28.48, -48.78)",
        "atual": atual,
        "pico_mare_24h": pico_mare_24h,
        "pico_vento_sul_24h": pico_sul_24h,
        "total_horas_gravadas": len(registros),
    }
    saida = DATA_DIR / "contorno_jusante_laguna.json"
    saida.write_text(json.dumps(resumo, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"[OK] contorno_jusante atualizado ({len(registros)} horas).")
    print(f"     Atual ({atual['timestamp']}): maré={atual['mare_msl_m']:+.2f} m | vento={atual['vento_kmh']} km/h ({atual['vento_dir_graus']}°) | comp_Sul={atual['componente_sul_kmh']} km/h | {atual['risco_remanso']}")
    print(f"     Pico maré 24h: {pico_mare_24h['mare_msl_m']:+.2f} m em {pico_mare_24h['timestamp']} ({pico_mare_24h['risco_remanso']})")


if __name__ == "__main__":
    coletar()
