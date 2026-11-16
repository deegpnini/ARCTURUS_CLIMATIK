#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Camada 0 — saúde das fontes + ICA simples (0–100)."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
HEALTH = BASE / "resultados" / "health_fontes.json"
META = BASE / "data" / "chuva_bacia_meta.json"
CSV = BASE / "data" / "chuva_bacia_openmeteo.csv"
OUT = BASE / "resultados" / "ica_atual.json"


def ping_openmeteo(url: str, params: dict) -> bool:
    try:
        r = requests.get(url, params=params, timeout=20)
        return r.status_code == 200
    except Exception:
        return False


def main():
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    agora = datetime.now()

    archive_ok = ping_openmeteo(
        "https://archive-api.open-meteo.com/v1/archive",
        {
            "latitude": -28.42,
            "longitude": -49.10,
            "start_date": (agora.date()).isoformat(),
            "end_date": (agora.date()).isoformat(),
            "hourly": "precipitation",
        },
    )
    forecast_ok = ping_openmeteo(
        "https://api.open-meteo.com/v1/forecast",
        {
            "latitude": -28.42,
            "longitude": -49.10,
            "hourly": "precipitation",
            "forecast_days": 1,
        },
    )

    cache_ok = CSV.exists()
    idade_h = None
    if cache_ok:
        try:
            df = pd.read_csv(CSV, index_col=0, parse_dates=True)
            ts_max = pd.to_datetime(df.index, errors="coerce").max()
            if pd.notna(ts_max):
                idade_h = (agora - ts_max.to_pydatetime()).total_seconds() / 3600.0
        except Exception:
            pass

    # Postgres / ERAB — tentativa leve
    erab_ok = False
    try:
        from src.relatorios.postgres_db import get_postgres_connection

        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT timestamp FROM leituras ORDER BY timestamp DESC LIMIT 1")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row:
            ts = row[0]
            if hasattr(ts, "timestamp"):
                idade_l = (agora - ts).total_seconds() / 60.0
            else:
                idade_l = (agora - pd.Timestamp(ts).to_pydatetime()).total_seconds() / 60.0
            erab_ok = idade_l <= 45
    except Exception:
        erab_ok = False

    health = {
        "openmeteo_archive": "ONLINE" if archive_ok else "OFFLINE",
        "openmeteo_forecast": "ONLINE" if forecast_ok else "OFFLINE",
        "cache_chuva": "ONLINE" if cache_ok else "OFFLINE",
        "erab_postgres": "ONLINE" if erab_ok else "OFFLINE",
        "idade_chuva_horas": None if idade_h is None else round(idade_h, 2),
        "atualizado_em": agora.isoformat(timespec="seconds"),
    }
    HEALTH.write_text(json.dumps(health, indent=2), encoding="utf-8")

    # Verifica se a ANA tem dados recentes (se o endpoint retornou items vazios)
    ana_ok = health.get("ana_hidroweb", "UNKNOWN") == "ONLINE"
    
    # ICA: frescor 40 + fontes 30 + pipeline 30
    frescor = 0
    if idade_h is not None:
        if idade_h <= 3:
            frescor = 40
        elif idade_h <= 6:
            frescor = 25
        elif idade_h <= 12:
            frescor = 15
        else:
            frescor = 5
    if erab_ok:
        frescor = min(40, frescor + 10)

    fontes = 0
    if archive_ok:
        fontes += 15
    if forecast_ok:
        fontes += 10
    if cache_ok:
        fontes += 5

    pipeline = 10  # script rodou
    if erab_ok:
        pipeline += 10
    if cache_ok and (idade_h is not None and idade_h <= 6):
        pipeline += 10

    ica = frescor + fontes + pipeline
    nivel = "ALTA" if ica >= 70 else ("MEDIA" if ica >= 45 else "BAIXA")
    ica_doc = {
        "ica": ica,
        "nivel": nivel,
        "frescor": frescor,
        "fontes": fontes,
        "pipeline": pipeline,
        "health": health,
    }
    OUT.write_text(json.dumps(ica_doc, indent=2), encoding="utf-8")
    print(json.dumps(ica_doc, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
