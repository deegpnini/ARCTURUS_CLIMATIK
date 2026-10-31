#!/usr/bin/env python3
"""Update the basin's hourly precipitation history from Open-Meteo Archive."""

import logging
import os
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import requests


BASE_DIR = Path(__file__).resolve().parents[2]
CSV_PATH = BASE_DIR / "data" / "chuva_bacia_openmeteo.csv"
API_URL = "https://archive-api.open-meteo.com/v1/archive"
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
LOG = logging.getLogger("baixar_chuva_bacia")


def baixar_ponto(session, nome, coordenadas, inicio, fim):
    latitude, longitude = coordenadas
    response = session.get(
        API_URL,
        params={
            "latitude": latitude,
            "longitude": longitude,
            "start_date": inicio.isoformat(),
            "end_date": fim.isoformat(),
            "hourly": "precipitation",
            "timezone": "America/Sao_Paulo",
        },
        timeout=60,
    )
    response.raise_for_status()
    hourly = response.json().get("hourly")
    if not hourly or not {"time", "precipitation"}.issubset(hourly):
        raise ValueError(f"Resposta horária incompleta para o ponto {nome}")
    if len(hourly["time"]) != len(hourly["precipitation"]):
        raise ValueError(f"Séries com tamanhos diferentes para o ponto {nome}")

    return pd.Series(
        hourly["precipitation"],
        index=pd.to_datetime(hourly["time"]),
        name=nome,
        dtype="float64",
    )


def coletar_ultimos_30_dias(session=None, hoje=None):
    """Fetch the last 30 calendar days, including today, for each basin point."""
    session = session or requests.Session()
    hoje = hoje or date.today()
    inicio = hoje - timedelta(days=29)
    series = []

    for index, (nome, coordenadas) in enumerate(PONTOS.items()):
        LOG.info("Baixando chuva horária: %s (%d/%d)", nome, index + 1, len(PONTOS))
        serie = baixar_ponto(session, nome, coordenadas, inicio, hoje)
        series.append(serie)
        if index + 1 < len(PONTOS):
            time.sleep(1)

    chuva = pd.concat(series, axis=1)
    chuva.index.name = "timestamp"
    return chuva.reindex(columns=PONTOS)


def atualizar_csv(caminho=CSV_PATH, chuva_nova=None):
    if chuva_nova is None or chuva_nova.empty:
        raise ValueError("A coleta não retornou dados; CSV existente não será alterado.")

    caminho = Path(caminho)
    caminho.parent.mkdir(parents=True, exist_ok=True)
    chuva_nova = chuva_nova.copy()
    chuva_nova.index = pd.to_datetime(chuva_nova.index, errors="raise")
    chuva_nova = chuva_nova.reindex(columns=PONTOS)

    if caminho.exists():
        existente = pd.read_csv(caminho, index_col=0, parse_dates=True)
        existente.index = pd.to_datetime(existente.index, errors="coerce")
        existente = existente.loc[~existente.index.isna()]
        existente = existente.reindex(columns=PONTOS)
        combinado = pd.concat([existente, chuva_nova])
    else:
        combinado = chuva_nova

    combinado = combinado[~combinado.index.duplicated(keep="last")].sort_index()
    combinado.index.name = "timestamp"
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=caminho.parent,
            prefix=f".{caminho.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:
            temporary_path = Path(temporary_file.name)
            combinado.to_csv(temporary_file, float_format="%.4f")
        os.replace(temporary_path, caminho)
        temporary_path = None
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
    return combinado


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        chuva_nova = coletar_ultimos_30_dias()
        atualizado = atualizar_csv(chuva_nova=chuva_nova)
    except (requests.RequestException, ValueError, OSError, pd.errors.ParserError):
        LOG.exception("Falha ao atualizar chuva da bacia; arquivo anterior preservado.")
        raise SystemExit(1)

    LOG.info(
        "CSV atualizado: %s | linhas=%d | pontos=%d | período=%s a %s",
        CSV_PATH,
        len(atualizado),
        len(PONTOS),
        atualizado.index.min(),
        atualizado.index.max(),
    )


if __name__ == "__main__":
    main()
