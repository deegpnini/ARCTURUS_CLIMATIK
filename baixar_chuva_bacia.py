#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Atualiza data/chuva_bacia_openmeteo.csv com fallback:
   1) archive-api (histórico recente)
   2) forecast-api + past_days
   3) mantém CSV existente (cache)
"""
from __future__ import annotations

import json
import time
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import requests

BASE = Path(__file__).resolve().parent
OUT_CSV = BASE / "data" / "chuva_bacia_openmeteo.csv"
META_JSON = BASE / "data" / "chuva_bacia_meta.json"
HEALTH = BASE / "resultados" / "health_fontes.json"

PONTOS = {
    "lauro_muller": (-28.393, -49.396),
    "orleans": (-28.360, -49.295),
    "grao_para": (-28.181, -49.225),
    "braco_norte": (-28.275, -49.168),
    "sao_ludgero": (-28.316, -49.183),
    "rio_fortuna": (-28.122, -49.114),
    "pedras_grandes": (-28.434, -49.188),
    "pouso": (-28.4206, -49.1064),
}

ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT = 45
RETRIES = 3


def _get(url: str, params: dict) -> dict | None:
    last = None
    for i in range(RETRIES):
        try:
            r = requests.get(url, params=params, timeout=TIMEOUT)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
        except Exception as e:
            last = str(e)
        time.sleep(2 * (i + 1))
    print(f"[AVISO] falha {url}: {last}")
    return None


def baixar_archive(dias: int = 14) -> pd.DataFrame | None:
    fim = date.today()
    ini = fim - timedelta(days=dias)
    out = {}
    for nome, (lat, lon) in PONTOS.items():
        data = _get(
            ARCHIVE_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "start_date": ini.isoformat(),
                "end_date": fim.isoformat(),
                "hourly": "precipitation",
                "timezone": "America/Sao_Paulo",
            },
        )
        if not data or "hourly" not in data:
            return None
        h = data["hourly"]
        out[nome] = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
        time.sleep(0.4)
    df = pd.DataFrame(out)
    df.index.name = "timestamp"
    return df.sort_index()


def baixar_forecast(past_days: int = 7) -> pd.DataFrame | None:
    out = {}
    for nome, (lat, lon) in PONTOS.items():
        data = _get(
            FORECAST_URL,
            {
                "latitude": lat,
                "longitude": lon,
                "hourly": "precipitation",
                "past_days": past_days,
                "forecast_days": 1,
                "timezone": "America/Sao_Paulo",
            },
        )
        if not data or "hourly" not in data:
            return None
        h = data["hourly"]
        out[nome] = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
        time.sleep(0.3)
    df = pd.DataFrame(out)
    df.index.name = "timestamp"
    return df.sort_index()


def merge_com_cache(novo: pd.DataFrame) -> pd.DataFrame:
    if not OUT_CSV.exists():
        return novo
    try:
        velho = pd.read_csv(OUT_CSV, index_col=0, parse_dates=True)
        velho.index = pd.to_datetime(velho.index, errors="coerce")
        velho = velho.loc[~velho.index.isna()]
        # alinha colunas
        for c in novo.columns:
            if c not in velho.columns:
                velho[c] = pd.NA
        for c in velho.columns:
            if c not in novo.columns:
                novo[c] = pd.NA
        cols = sorted(set(velho.columns) | set(novo.columns))
        velho, novo = velho[cols], novo[cols]
        comb = pd.concat([velho, novo])
        comb = comb[~comb.index.duplicated(keep="last")].sort_index()
        return comb
    except Exception as e:
        print(f"[AVISO] merge cache falhou: {e}")
        return novo


def salvar_meta(origem: str, df: pd.DataFrame | None, ok: bool):
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "origem": origem,
        "ok": ok,
        "atualizado_em": datetime.now().isoformat(timespec="seconds"),
        "linhas": int(len(df)) if df is not None else 0,
        "ts_min": str(df.index.min()) if df is not None and len(df) else None,
        "ts_max": str(df.index.max()) if df is not None and len(df) else None,
    }
    META_JSON.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    # health parcial
    HEALTH.parent.mkdir(parents=True, exist_ok=True)
    health = {}
    if HEALTH.exists():
        try:
            health = json.loads(HEALTH.read_text(encoding="utf-8"))
        except Exception:
            health = {}
    health["openmeteo_archive"] = "ONLINE" if origem == "archive" else health.get("openmeteo_archive", "OFFLINE")
    health["openmeteo_forecast"] = "ONLINE" if origem == "forecast" else health.get("openmeteo_forecast", "UNKNOWN")
    if origem == "archive":
        health["openmeteo_archive"] = "ONLINE"
    if origem == "forecast":
        health["openmeteo_forecast"] = "ONLINE"
        health["openmeteo_archive"] = health.get("openmeteo_archive", "OFFLINE")
        if health["openmeteo_archive"] != "ONLINE":
            health["openmeteo_archive"] = "OFFLINE"
    if origem == "cache":
        health["openmeteo_archive"] = "OFFLINE"
        health["openmeteo_forecast"] = "OFFLINE"
        health["cache_chuva"] = "ONLINE"
    health["cache_chuva"] = "ONLINE" if OUT_CSV.exists() else "OFFLINE"
    health["atualizado_em"] = meta["atualizado_em"]
    HEALTH.write_text(json.dumps(health, indent=2), encoding="utf-8")
    print(json.dumps(meta, ensure_ascii=False))


def main():
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)

    print("==> tentando archive-api ...")
    df = baixar_archive(dias=14)
    origem = "archive"

    if df is None or df.empty:
        print("==> archive falhou; tentando forecast + past_days=7 ...")
        df = baixar_forecast(past_days=7)
        origem = "forecast"

    if df is None or df.empty:
        if OUT_CSV.exists():
            print("==> APIs falharam; mantendo cache local")
            try:
                df = pd.read_csv(OUT_CSV, index_col=0, parse_dates=True)
                salvar_meta("cache", df, ok=True)
                print(f"[OK] cache {OUT_CSV} shape={df.shape}")
                return
            except Exception as e:
                salvar_meta("falha", None, ok=False)
                raise SystemExit(f"[ERRO] sem API e sem cache: {e}")
        salvar_meta("falha", None, ok=False)
        raise SystemExit("[ERRO] sem dados de chuva")

    df = merge_com_cache(df)
    df.to_csv(OUT_CSV)
    salvar_meta(origem, df, ok=True)
    print(f"[OK] {origem} → {OUT_CSV} shape={df.shape} "
          f"{df.index.min()} → {df.index.max()}")


if __name__ == "__main__":
    main()
