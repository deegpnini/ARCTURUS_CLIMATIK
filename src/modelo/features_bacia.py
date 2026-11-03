# -*- coding: utf-8 -*-
"""Features de chuva na bacia a partir de data/chuva_bacia_openmeteo.csv."""
from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_BACIA = BASE_DIR / "data" / "chuva_bacia_openmeteo.csv"
LOGGER = logging.getLogger(__name__)

FEATURE_NAMES = (
    "bacia_lag_4h",
    "bacia_lag_6h",
    "bacia_lag_8h",
    "bacia_3h",
    "bacia_6h",
    "bacia_12h",
    "bacia_max1h",
    "bacia_pontos_forte",
)


def _vazio() -> dict:
    return {k: float("nan") for k in FEATURE_NAMES}


def calcular_features_bacia(data_alvo) -> dict:
    """Calcula features de bacia até data_alvo (sem leakage futuro)."""
    if not ARQUIVO_BACIA.exists():
        LOGGER.warning("CSV de bacia ausente: %s", ARQUIVO_BACIA)
        return _vazio()

    try:
        df = pd.read_csv(ARQUIVO_BACIA, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df.loc[~df.index.isna()].sort_index()
        if df.empty:
            return _vazio()

        data_alvo = pd.Timestamp(data_alvo)
        if df.index.max() > data_alvo:
            LOGGER.warning(
                "Possível leakage na chuva (%s > %s); linhas futuras serão ignoradas.",
                df.index.max(),
                data_alvo,
            )

        df = df[df.index <= data_alvo]
        if df.empty:
            return _vazio()

        cols = df.select_dtypes(include=[np.number]).columns
        if len(cols) == 0:
            return _vazio()

        # série horária = média espacial dos pontos
        media = df[cols].mean(axis=1)

        def lag(h: int):
            if len(media) <= h:
                return float("nan")
            v = media.shift(h).iloc[-1]
            return float(v) if pd.notna(v) else float("nan")

        def soma(h: int):
            if len(media) < h:
                return float("nan")
            janela = media.iloc[-h:]
            if janela.isna().any():
                n_nan = int(janela.isna().sum().sum())
                LOGGER.warning("Janela de %dh contém %d valores NaN; não serão convertidos em zero; retornando NaN.", h, n_nan)
                return float("nan")
            v = janela.sum()
            return float(v) if pd.notna(v) else float("nan")

        # max1h: máximo da média horária na última hora (1 passo se horário)
        max1h = media.iloc[-1]
        max1h = float(max1h) if pd.notna(max1h) else float("nan")

        ultima = df[cols].iloc[-1]
        pontos_forte = (
            float((ultima.dropna() > 5.0).sum())
            if ultima.notna().any()
            else float("nan")
        )

        return {
            "bacia_lag_4h": lag(4),
            "bacia_lag_6h": lag(6),
            "bacia_lag_8h": lag(8),
            "bacia_3h": soma(3),
            "bacia_6h": soma(6),
            "bacia_12h": soma(12),
            "bacia_max1h": max1h,
            "bacia_pontos_forte": pontos_forte,
        }
    except Exception:
        LOGGER.exception("Falha features_bacia")
        return _vazio()
