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

# Lista de features (o modelo v10 precisa saber quais são)
FEATURE_NAMES = (
    "bacia_lag_4h", "bacia_lag_6h", "bacia_lag_8h",
    "bacia_3h", "bacia_6h", "bacia_12h",
    "bacia_max1h", "bacia_pontos_forte",
    "chuva_24h", "chuva_72h", "chuva_7d",
    "api_3d", "api_7d", "api_14d",
    "chuva_orleans_lag_15h",
    "chuva_lauro_muller_lag_15h",
    "chuva_braco_norte_lag_15h",
    "chuva_grao_para_lag_14h",
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
                "Chuva com linhas > origem (%s > %s); linhas futuras serão ignoradas.",
                df.index.max(), data_alvo,
            )

        df = df[df.index <= data_alvo]
        if df.empty:
            return _vazio()

        cols = df.select_dtypes(include=[np.number]).columns
        if len(cols) == 0:
            return _vazio()

        media = df[cols].mean(axis=1)

        def lag_media(h: int):
            if len(media) <= h:
                return float("nan")
            v = media.shift(h).iloc[-1]
            return float(v) if pd.notna(v) else float("nan")

        def lag_coluna(col: str, h: int):
            if col not in df.columns:
                return float("nan")
            serie = df[col].dropna()
            if len(serie) <= h:
                return float("nan")
            v = serie.shift(h).iloc[-1]
            return float(v) if pd.notna(v) else float("nan")

        def soma(h: int):
            if len(media) < h:
                return float("nan")
            janela = media.iloc[-h:]
            if janela.isna().any():
                return float("nan")
            return float(janela.sum())

        def api(h_dias: int):
            horas = h_dias * 24
            if len(media) < horas:
                return float("nan")
            janela = media.iloc[-horas:]
            valor = 0.0
            for v in janela:
                if pd.notna(v):
                    valor = v + 0.9 * valor
            return float(valor)

        max1h = media.iloc[-1]
        max1h = float(max1h) if pd.notna(max1h) else float("nan")

        ultima = df[cols].iloc[-1]
        pontos_forte = float((ultima.dropna() > 5.0).sum()) if ultima.notna().any() else float("nan")

        return {
            "bacia_lag_4h": lag_media(4),
            "bacia_lag_6h": lag_media(6),
            "bacia_lag_8h": lag_media(8),
            "bacia_3h": soma(3),
            "bacia_6h": soma(6),
            "bacia_12h": soma(12),
            "bacia_max1h": max1h,
            "bacia_pontos_forte": pontos_forte,
            "chuva_24h": soma(24),
            "chuva_72h": soma(72),
            "chuva_7d": soma(168),
            "api_3d": api(3),
            "api_7d": api(7),
            "api_14d": api(14),
            # Features de lag por cidade (o achado hidrológico)
            "chuva_orleans_lag_15h": lag_coluna("orleans", 15),
            "chuva_lauro_muller_lag_15h": lag_coluna("lauro_muller", 15),
            "chuva_braco_norte_lag_15h": lag_coluna("braco_norte", 15),
            "chuva_grao_para_lag_14h": lag_coluna("grao_para", 14),
        }
    except Exception:
        LOGGER.exception("Falha features_bacia")
        return _vazio()
