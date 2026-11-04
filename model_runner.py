#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor do modo sombra v2 — LightGBM v8 (delta de cota).
Features de cota + bacia (Open-Meteo). NUNCA dispara alerta.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import numbers
from datetime import datetime, timedelta
from pathlib import Path

import lightgbm as lgb
import pandas as pd

from src.modelo.features_bacia import calcular_features_bacia
from src.relatorios.postgres_db import get_postgres_connection
from persistir_shadow import registrar

MANIFESTO = "modelos/manifesto_v8.json"
MODELOS = {
    "1h": "modelos/modelo_delta_1h_v8_final.txt",
    "3h": "modelos/modelo_delta_3h_v8_final.txt",
    "6h": "modelos/modelo_delta_6h_v9.txt",
}
MODEL_VERSION = "v8_final_bacia"
BASE_DIR = Path(__file__).resolve().parent
RAIN_CSV = BASE_DIR / "data" / "chuva_bacia_openmeteo.csv"
MAX_OBSERVATION_AGE = timedelta(minutes=45)
MAX_RAIN_AGE = timedelta(hours=6)
LOGGER = logging.getLogger(__name__)



def verificar_frescor(ts_observacao, limite_min=45):
    """Retorna True se a leitura for mais antiga que o limite (minutos)."""
    from datetime import datetime
    if ts_observacao is None:
        return True
    if isinstance(ts_observacao, str):
        ts_observacao = datetime.fromisoformat(ts_observacao)
    idade = (datetime.now() - ts_observacao).total_seconds() / 60
    return idade > limite_min


def carregar_features():
    with open(MANIFESTO, encoding="utf-8") as f:
        return json.load(f)["features"]


def puxar_leituras(n=200):
    conn = get_postgres_connection()
    try:
        cur = conn.cursor()
        cur.execute(
            """
            SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, chuva_pior_caso_mm
            FROM leituras
            WHERE cota_cm IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT %s
            """,
            (n,),
        )
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    if not rows:
        return None
    cols = ["timestamp", "cota_cm", "vz_cm_h", "az_cm_h2", "chuva_pior_caso_mm"]
    return pd.DataFrame(rows, columns=cols).sort_values("timestamp").reset_index(drop=True)


def _lag_cota(df: pd.DataFrame, passos: int):
    """Passos de 15 min: 1=15m, 2=30m, 4=60m, 12=3h, 24=6h, 48=12h, 96=24h."""
    if len(df) <= passos:
        return float("nan")
    v = df.iloc[-(passos + 1)]["cota_cm"]
    return float(v) if pd.notna(v) else float("nan")


def calcular_features(df: pd.DataFrame, features: list) -> pd.DataFrame:
    ultima = df.iloc[-1]
    ts = pd.to_datetime(ultima["timestamp"])
    cota = float(ultima["cota_cm"])
    vz = ultima["vz_cm_h"]
    az = ultima["az_cm_h2"]

    base = {
        "cota": cota,
        "cota_lag_15m": _lag_cota(df, 1),
        "cota_lag_30m": _lag_cota(df, 2),
        "cota_lag_60m": _lag_cota(df, 4),
        "cota_lag_180m": _lag_cota(df, 12),
        "cota_lag_360m": _lag_cota(df, 24),
        "cota_lag_720m": _lag_cota(df, 48),
        "cota_lag_1440m": _lag_cota(df, 96),
        "delta_15m": (float(vz) / 4.0) if pd.notna(vz) else float("nan"),
        "delta_60m": float(vz) if pd.notna(vz) else float("nan"),
        "aceleracao_1h": float(az) if pd.notna(az) else float("nan"),
        "sin_hora": math.sin(2 * math.pi * ts.hour / 24),
        "cos_hora": math.cos(2 * math.pi * ts.hour / 24),
        "sin_dia_ano": math.sin(2 * math.pi * ts.dayofyear / 365),
        "cos_dia_ano": math.cos(2 * math.pi * ts.dayofyear / 365),
    }

    # delta_180m ≈ (cota - cota_3h) / 3
    c3 = base["cota_lag_180m"]
    if pd.notna(c3):
        base["delta_180m"] = (cota - c3) / 3.0
    else:
        base["delta_180m"] = float("nan")

    # janela 12h (48 passos de 15 min)
    janela = df.iloc[-48:]["cota_cm"] if len(df) >= 2 else df["cota_cm"]
    base["cota_std_12h"] = float(janela.std()) if len(janela) >= 2 else float("nan")
    base["cota_max_12h"] = float(janela.max()) if len(janela) else float("nan")
    base["cota_min_12h"] = float(janela.min()) if len(janela) else float("nan")

    base.update(calcular_features_bacia(ts))
    row = {f: base.get(f, float("nan")) for f in features}
    return pd.DataFrame([row])[features]


def calcular_features_hash(X: pd.DataFrame) -> str:
    valores = {}
    for nome, valor in X.iloc[0].items():
        if pd.isna(valor):
            valores[nome] = None
        elif isinstance(valor, numbers.Real):
            valores[nome] = float(valor)
        else:
            valores[nome] = str(valor)
    payload = json.dumps(valores, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.md5(payload.encode("utf-8")).hexdigest()


def ultima_chuva_observada(ts_origem, caminho=RAIN_CSV):
    try:
        chuva = pd.read_csv(caminho, index_col=0, parse_dates=True)
    except Exception:
        LOGGER.exception("Falha ao ler CSV de chuva")
        return None
    chuva.index = pd.to_datetime(chuva.index, errors="coerce")
    chuva = chuva.loc[~chuva.index.isna()].sort_index()
    if chuva.empty:
        return None
    if chuva.index.max() > ts_origem:
        LOGGER.warning(
            "Possível leakage no CSV de chuva: máximo=%s, ts_origem=%s. Dados posteriores à origem não serão considerados.",
            chuva.index.max(), ts_origem
        )
    elegiveis = chuva.index[chuva.index <= ts_origem]
    return elegiveis.max() if len(elegiveis) else None


def motivos_dados_vencidos(ts_observacao, ts_predicao, ts_chuva):
    motivos = []
    idade = ts_predicao - ts_observacao
    if idade < timedelta(0):
        motivos.append("leitura no futuro")
    elif idade > MAX_OBSERVATION_AGE:
        motivos.append(f"leitura com {idade.total_seconds()/60:.1f} min")
    if ts_chuva is None:
        motivos.append("sem chuva elegível")
    else:
        idade_c = ts_observacao - ts_chuva
        if idade_c < timedelta(0):
            motivos.append("chuva no futuro")
        elif idade_c > MAX_RAIN_AGE:
            motivos.append(f"chuva com {idade_c.total_seconds()/3600:.1f} h")
    return motivos


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    features = carregar_features()
    df = puxar_leituras()
    if df is None or len(df) == 0:
        print("[AVISO] Sem leituras no PostgreSQL.")
        return

    ts_predicao = datetime.now()
    ts_observacao = pd.Timestamp(df.iloc[-1]["timestamp"]).to_pydatetime()
    evento_id = f"cron_{ts_predicao.strftime('%Y%m%d_%H%M')}"
    cota_atual = float(df.iloc[-1]["cota_cm"])

    ts_chuva = ultima_chuva_observada(pd.Timestamp(ts_observacao))
    stale_motivos = motivos_dados_vencidos(
        pd.Timestamp(ts_observacao), pd.Timestamp(ts_predicao), ts_chuva
    )
    if stale_motivos:
        LOGGER.error("Inferência cancelada: %s", "; ".join(stale_motivos))
        for h in MODELOS:
            registrar(
                timestamp=ts_predicao,
                evento_id=evento_id,
                y_pred=None,
                horizonte=h,
                cota_atual=cota_atual,
                ts_observacao=ts_observacao,
                ts_predicao=ts_predicao,
                model_version=MODEL_VERSION,
                stale=True,
                features={"stale": True, "motivo": "; ".join(stale_motivos)},
            )
        return

    X = calcular_features(df, features)
    # log de cobertura de bacia
    bacia_cols = [c for c in X.columns if c.startswith("bacia_")]
    n_ok = int(X[bacia_cols].notna().sum(axis=1).iloc[0]) if bacia_cols else 0
    print(f"[FEATURES] bacia preenchidas={n_ok}/{len(bacia_cols)} hash={calcular_features_hash(X)[:8]}")

    features_hash = calcular_features_hash(X)
    # Converte X (pandas) para dict serializável (float)
    features_dict = {
        k: (None if pd.isna(v) else float(v))
        for k, v in X.iloc[0].items()
    }

    for h, path in MODELOS.items():
        try:
            modelo = lgb.Booster(model_file=path)
            y_pred = float(modelo.predict(X)[0])
            registrar(
                timestamp=ts_predicao,
                evento_id=evento_id,
                y_pred=y_pred,
                horizonte=h,
                cota_atual=cota_atual,
                ts_observacao=ts_observacao,
                ts_predicao=ts_predicao,
                model_version=MODEL_VERSION,
                features_hash=features_hash,
                features=features_dict,
            )
        except Exception as e:
            print(f"[ERRO] Modelo {h}: {e}")
    print(f"[OK] sombra v2. Cota={cota_atual} cm")


if __name__ == "__main__":
    main()
