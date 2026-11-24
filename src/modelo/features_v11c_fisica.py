# -*- coding: utf-8 -*-
"""
features_v11c_fisica.py — Engenharia de atributos fisicos para o motor v11c (modo sombra).
Separa explicitamente os 3 bracos fluviais da Bacia do Rio Tubarao (com defasagens
hidrologicas proprias) e acopla a condicao de contorno de jusante (mare + vento sul em Laguna).
Combina Open-Meteo (serie horaria continua de montante) + Defesa Civil SC (telemetria
observada do baixo curso/sul) sem vazamento temporal. Nao altera o motor v8.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
import numpy as np
import pandas as pd

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.relatorios.postgres_db import get_postgres_connection

BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_BACIA = BASE_DIR / "data" / "chuva_bacia_openmeteo.csv"
ARQUIVO_DCSC_HIST = BASE_DIR / "data" / "historico_defesacivil_bacia.jsonl"
LOGGER = logging.getLogger(__name__)

# Colunas reais presentes em data/chuva_bacia_openmeteo.csv:
# ['lauro_muller', 'orleans', 'grao_para', 'braco_norte', 'sao_ludgero', 'rio_fortuna', 'pedras_grandes', 'pouso']
COLS_RAMO_OESTE = ["lauro_muller", "orleans", "pedras_grandes"]               # Transito 8-12h
COLS_RAMO_NORTE = ["braco_norte", "sao_ludgero", "grao_para", "rio_fortuna"]   # Transito 5-8h
COLS_TRANSICAO_JUSANTE = ["pouso"]                                             # Pouso Redondo / eixo baixo-medio

FEATURES_V11C_FISICA = (
    # 1. Ramo Oeste (Alto Tubarao - resposta rapida de serra, lag 8-12h)
    "oeste_chuva_3h",
    "oeste_chuva_6h",
    "oeste_chuva_24h",
    "oeste_lag_8h",
    "oeste_lag_10h",
    "oeste_lag_12h",
    # 2. Ramo Norte (Braco do Norte / Sao Ludgero - maior area de contribuicao, lag 5-8h)
    "norte_chuva_3h",
    "norte_chuva_6h",
    "norte_chuva_24h",
    "norte_lag_5h",
    "norte_lag_7h",
    "norte_lag_8h",
    # 3. Eixo Transicao / Leste-Sul (Pouso + Defesa Civil Urussanga/Sul, lag 4-6h)
    "leste_sul_chuva_6h",
    "leste_sul_chuva_24h",
    "transicao_lag_4h",
    "transicao_lag_6h",
    # 4. Planicie / Baixo Curso Observado (Defesa Civil SC - Tubarao Guarda)
    "planicie_dcsc_1h",
    "planicie_dcsc_6h",
    "planicie_dcsc_24h",
    "dcsc_max_bacia_6h",
    "dcsc_max_bacia_24h",
    # 5. Assimetria espacial (qual braco domina o evento)
    "raz_oeste_norte_24h",
    "gradiente_cabeceira_planicie_6h",
    # 6. Condicao de Contorno de Jusante (Laguna - mare e empilhamento por vento sul)
    "jusante_mare_msl_m",
    "jusante_mare_delta_3h_m",
    "jusante_vento_sul_kmh",
    "jusante_vento_sul_max_6h_kmh",
    "indice_bloqueio_foz",
)


def _vazio_fisico() -> dict:
    return {k: float("nan") for k in FEATURES_V11C_FISICA}


def _calcular_3_bracos_openmeteo(data_alvo: pd.Timestamp) -> dict:
    out = {}
    if not ARQUIVO_BACIA.exists():
        return out

    df = pd.read_csv(ARQUIVO_BACIA, index_col=0, parse_dates=True)
    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.loc[~df.index.isna()].sort_index()
    df = df[df.index <= data_alvo]
    if df.empty:
        return out

    def _serie(cols_alvo: list[str]) -> pd.Series:
        presentes = [c for c in cols_alvo if c in df.columns]
        if not presentes:
            return pd.Series(dtype=float)
        return df[presentes].mean(axis=1)

    s_oeste = _serie(COLS_RAMO_OESTE)
    s_norte = _serie(COLS_RAMO_NORTE)
    s_trans = _serie(COLS_TRANSICAO_JUSANTE)

    def _soma(s: pd.Series, h: int) -> float:
        if len(s) < h:
            return float("nan")
        j = s.iloc[-h:]
        return float(j.sum()) if not j.isna().all() else float("nan")

    def _lag(s: pd.Series, h: int) -> float:
        if len(s) <= h:
            return float("nan")
        v = s.shift(h).iloc[-1]
        return float(v) if pd.notna(v) else float("nan")

    o24 = _soma(s_oeste, 24)
    n24 = _soma(s_norte, 24)

    out.update({
        "oeste_chuva_3h": _soma(s_oeste, 3),
        "oeste_chuva_6h": _soma(s_oeste, 6),
        "oeste_chuva_24h": o24,
        "oeste_lag_8h": _lag(s_oeste, 8),
        "oeste_lag_10h": _lag(s_oeste, 10),
        "oeste_lag_12h": _lag(s_oeste, 12),
        "norte_chuva_3h": _soma(s_norte, 3),
        "norte_chuva_6h": _soma(s_norte, 6),
        "norte_chuva_24h": n24,
        "norte_lag_5h": _lag(s_norte, 5),
        "norte_lag_7h": _lag(s_norte, 7),
        "norte_lag_8h": _lag(s_norte, 8),
        "transicao_lag_4h": _lag(s_trans, 4),
        "transicao_lag_6h": _lag(s_trans, 6),
        "leste_sul_chuva_6h": _soma(s_trans, 6),
        "leste_sul_chuva_24h": _soma(s_trans, 24),
        "raz_oeste_norte_24h": float((o24 + 0.1) / (n24 + 0.1)) if pd.notna(o24) and pd.notna(n24) else float("nan"),
    })
    return out


def _calcular_dcsc_observado(data_alvo: pd.Timestamp) -> dict:
    """Extrai o snapshot mais recente da Defesa Civil SC <= data_alvo (janela maxima 2h)."""
    out = {}
    if not ARQUIVO_DCSC_HIST.exists():
        return out

    melhor_ts = None
    melhor_reg = None
    for linha in ARQUIVO_DCSC_HIST.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not linha.strip():
            continue
        try:
            reg = json.loads(linha)
            ts_raw = reg.get("timestamp_coleta") or reg.get("timestamp")
            if not ts_raw:
                continue
            ts_reg = pd.Timestamp(ts_raw)
            if ts_reg.tzinfo is not None:
                ts_reg = ts_reg.tz_convert("America/Sao_Paulo").tz_localize(None)
            if ts_reg <= data_alvo and (data_alvo - ts_reg) <= pd.Timedelta(hours=2):
                if melhor_ts is None or ts_reg > melhor_ts:
                    melhor_ts = ts_reg
                    melhor_reg = reg
        except Exception:
            continue

    if not melhor_reg or not isinstance(melhor_reg.get("estacoes"), list):
        return out

    plan_1h, plan_6h, plan_24h = [], [], []
    sul_6h, sul_24h = [], []
    bacia_6h, bacia_24h = [], []

    for est in melhor_reg["estacoes"]:
        if not isinstance(est, dict):
            continue
        cod = str(est.get("codigo", ""))
        trecho = str(est.get("trecho_bacia", "")).lower()
        c1 = est.get("chuva_1h_mm")
        c6 = est.get("chuva_6h_mm")
        c24 = est.get("chuva_24h_mm")

        if c6 is not None:
            bacia_6h.append(float(c6))
        if c24 is not None:
            bacia_24h.append(float(c24))

        # Tubarao - Guarda (Baixo Curso / Planicie)
        if cod == "DCSC-00048" or "guarda" in trecho or "baixo curso" in trecho:
            if c1 is not None:
                plan_1h.append(float(c1))
            if c6 is not None:
                plan_6h.append(float(c6))
            if c24 is not None:
                plan_24h.append(float(c24))

        # Urussanga / Sul-Leste
        if cod == "DCSC-00075" or "urussanga" in trecho or "sul" in trecho:
            if c6 is not None:
                sul_6h.append(float(c6))
            if c24 is not None:
                sul_24h.append(float(c24))

    if plan_1h:
        out["planicie_dcsc_1h"] = max(plan_1h)
    if plan_6h:
        out["planicie_dcsc_6h"] = max(plan_6h)
    if plan_24h:
        out["planicie_dcsc_24h"] = max(plan_24h)
    if bacia_6h:
        out["dcsc_max_bacia_6h"] = max(bacia_6h)
    if bacia_24h:
        out["dcsc_max_bacia_24h"] = max(bacia_24h)
    if sul_6h:
        out["leste_sul_chuva_6h"] = max(sul_6h)
    if sul_24h:
        out["leste_sul_chuva_24h"] = max(sul_24h)

    return out


def _calcular_contorno_jusante(data_alvo: pd.Timestamp) -> dict:
    out = {}
    conn = None
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        ts_str = data_alvo.strftime("%Y-%m-%d %H:%M:%S")
        cur.execute(
            """
            SELECT timestamp, mare_msl_m, componente_sul_kmh
            FROM contorno_jusante
            WHERE timestamp <= %s::timestamp
              AND timestamp >= %s::timestamp - INTERVAL '12 hours'
            ORDER BY timestamp ASC;
            """,
            (ts_str, ts_str),
        )
        rows = cur.fetchall()
        cur.close()
        if not rows:
            return out

        df_j = pd.DataFrame(rows, columns=["timestamp", "mare_msl_m", "componente_sul_kmh"])
        mare_atual = float(df_j["mare_msl_m"].iloc[-1])
        vento_sul_atual = float(df_j["componente_sul_kmh"].iloc[-1])
        mare_3h_atras = float(df_j["mare_msl_m"].iloc[-4]) if len(df_j) >= 4 else float(df_j["mare_msl_m"].iloc[0])
        vento_sul_max_6h = float(df_j["componente_sul_kmh"].iloc[-6:].max())

        bloqueio = max(0.0, mare_atual) + 0.015 * max(0.0, vento_sul_max_6h)

        out.update({
            "jusante_mare_msl_m": round(mare_atual, 4),
            "jusante_mare_delta_3h_m": round(mare_atual - mare_3h_atras, 4),
            "jusante_vento_sul_kmh": round(vento_sul_atual, 2),
            "jusante_vento_sul_max_6h_kmh": round(vento_sul_max_6h, 2),
            "indice_bloqueio_foz": round(bloqueio, 4),
        })
    except Exception:
        LOGGER.exception("Falha ao consultar contorno_jusante")
    finally:
        if conn is not None:
            conn.close()
    return out


def calcular_features_v11c_fisica(data_alvo=None) -> dict:
    """Retorna o vetor completo de 28 features fisicas (3 bracos + DCSC + jusante) sem leakage futuro."""
    ts = pd.Timestamp.now() if data_alvo is None else pd.Timestamp(data_alvo)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/Sao_Paulo").tz_localize(None)

    res = _vazio_fisico()
    res.update(_calcular_3_bracos_openmeteo(ts))
    res.update(_calcular_dcsc_observado(ts))
    res.update(_calcular_contorno_jusante(ts))

    o6 = res.get("oeste_chuva_6h")
    n6 = res.get("norte_chuva_6h")
    p6 = res.get("planicie_dcsc_6h")
    if pd.notna(o6) and pd.notna(n6) and pd.notna(p6):
        res["gradiente_cabeceira_planicie_6h"] = round(float(max(o6, n6) - p6), 3)

    return res


if __name__ == "__main__":
    feats = calcular_features_v11c_fisica()
    nans = [k for k, v in feats.items() if pd.isna(v)]
    print(f"[OK] Features fisicas: {len(feats)} total | {len(nans)} NaN ({nans})")
    print(json.dumps(feats, indent=2, ensure_ascii=False))
