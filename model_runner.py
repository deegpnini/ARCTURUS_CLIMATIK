#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor do modo sombra (v1) — LightGBM v2 regressao (delta de cota).
Usa features disponiveis no PostgreSQL; features de lag/bacia ficam NaN.
Roda no cron a cada 15 min, persiste y_pred, NUNCA dispara alerta.
"""
import json
import hashlib
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

# --- CONFIG ---
MANIFESTO = "modelos/manifesto_v8.json"
MODELOS = {
    "1h": "modelos/modelo_delta_1h_v8_final.txt",
    "3h": "modelos/modelo_delta_3h_v8_final.txt",
    "6h": "modelos/modelo_delta_6h_v8_final.txt",
}
MODEL_VERSION = "v8_final"
BASE_DIR = Path(__file__).resolve().parent
RAIN_CSV = BASE_DIR / "data" / "chuva_bacia_openmeteo.csv"
MAX_OBSERVATION_AGE = timedelta(minutes=45)
MAX_RAIN_AGE = timedelta(hours=6)
LOGGER = logging.getLogger(__name__)

def carregar_features():
    with open(MANIFESTO, encoding="utf-8") as f:
        return json.load(f)["features"]

def puxar_leituras(n=96):
    """Ultimas n leituras do PostgreSQL (96 = 24h em passos de 15min)."""
    conn = get_postgres_connection()
    try:
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, chuva_pior_caso_mm
            FROM leituras
            WHERE cota_cm IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT %s
        """, (n,))
        rows = cur.fetchall()
        cur.close()
    finally:
        conn.close()
    if not rows:
        return None
    cols = ["timestamp", "cota_cm", "vz_cm_h", "az_cm_h2", "chuva_pior_caso_mm"]
    return pd.DataFrame(rows, columns=cols).sort_values("timestamp").reset_index(drop=True)

def calcular_features(df, features):
    """Calcula as features derivadas das leituras e da chuva na bacia."""
    ultima = df.iloc[-1]
    ts = pd.to_datetime(ultima["timestamp"])
    base = {
        "cota": ultima["cota_cm"],
        "delta_15m": ultima["vz_cm_h"] / 4 if pd.notna(ultima["vz_cm_h"]) else float("nan"),
        "delta_60m": ultima["vz_cm_h"] if pd.notna(ultima["vz_cm_h"]) else float("nan"),
        "aceleracao_1h": ultima["az_cm_h2"] if pd.notna(ultima["az_cm_h2"]) else float("nan"),
        "sin_hora": math.sin(2 * math.pi * ts.hour / 24),
        "cos_hora": math.cos(2 * math.pi * ts.hour / 24),
        "sin_dia_ano": math.sin(2 * math.pi * ts.dayofyear / 365),
        "cos_dia_ano": math.cos(2 * math.pi * ts.dayofyear / 365),
    }
    # Features de lag de cota: tentar calcular a partir do historico
    if len(df) >= 2:
        base["cota_lag_15m"] = df.iloc[-2]["cota_cm"] if len(df) >= 2 else float("nan")
    if len(df) >= 5:
        base["cota_lag_60m"] = df.iloc[-5]["cota_cm"]
    if len(df) >= 13:
        base["cota_lag_180m"] = df.iloc[-13]["cota_cm"]
    if len(df) >= 25:
        base["cota_lag_360m"] = df.iloc[-25]["cota_cm"]
    base.update(calcular_features_bacia(ts))
    row = {f: base.get(f, float("nan")) for f in features}
    return pd.DataFrame([row])[features]

def calcular_features_hash(X):
    """Hash canonical JSON for the exact feature row sent to the model."""
    valores = {}
    for nome, valor in X.iloc[0].items():
        if pd.isna(valor):
            valores[nome] = None
        elif isinstance(valor, numbers.Real):
            valores[nome] = float(valor)
        else:
            valores[nome] = str(valor)
    payload = json.dumps(
        valores, sort_keys=True, separators=(",", ":"), allow_nan=False
    )
    return hashlib.md5(payload.encode("utf-8")).hexdigest()

def ultima_chuva_observada(ts_origem, caminho=RAIN_CSV):
    """Return the newest rainfall timestamp no later than the observation."""
    try:
        chuva = pd.read_csv(caminho, index_col=0, parse_dates=True)
    except (OSError, ValueError, pd.errors.ParserError):
        LOGGER.exception("Não foi possível ler o CSV de chuva para validar frescor.")
        return None

    chuva.index = pd.to_datetime(chuva.index, errors="coerce")
    chuva = chuva.loc[~chuva.index.isna()].sort_index()
    if chuva.empty:
        LOGGER.error("CSV de chuva não contém timestamps válidos.")
        return None

    ts_mais_recente = chuva.index.max()
    if ts_mais_recente > ts_origem:
        LOGGER.warning(
            "Possível leakage no CSV de chuva: máximo=%s, ts_origem=%s. "
            "Dados posteriores à origem não serão considerados.",
            ts_mais_recente,
            ts_origem,
        )

    nan_count = int(chuva.isna().sum().sum())
    if nan_count:
        LOGGER.warning(
            "CSV de chuva contém %d valores NaN; nenhum será convertido em zero.",
            nan_count,
        )

    elegiveis = chuva.index[chuva.index <= ts_origem]
    return elegiveis.max() if len(elegiveis) else None

def motivos_dados_vencidos(ts_observacao, ts_predicao, ts_chuva):
    idade_leitura = ts_predicao - ts_observacao
    motivos = []
    if idade_leitura < timedelta(0):
        motivos.append("timestamp da leitura está no futuro")
    elif idade_leitura > MAX_OBSERVATION_AGE:
        motivos.append(f"leitura com {idade_leitura.total_seconds() / 60:.1f} min")

    if ts_chuva is None:
        motivos.append("sem timestamp de chuva elegível")
    else:
        idade_chuva = ts_observacao - ts_chuva
        if idade_chuva < timedelta(0):
            motivos.append("timestamp da chuva elegível está no futuro")
        elif idade_chuva > MAX_RAIN_AGE:
            motivos.append(f"chuva com {idade_chuva.total_seconds() / 3600:.1f} h")
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
        print("[AVISO] Sem leituras no PostgreSQL. Nada a fazer.")
        return

    ts_predicao = datetime.now()
    ts_observacao = pd.Timestamp(df.iloc[-1]["timestamp"]).to_pydatetime()
    evento_id = f"cron_{ts_predicao.strftime('%Y%m%d_%H%M')}"
    cota_atual = float(df.iloc[-1]["cota_cm"])

    ts_chuva = ultima_chuva_observada(pd.Timestamp(ts_observacao))
    motivos_stale = motivos_dados_vencidos(
        pd.Timestamp(ts_observacao),
        pd.Timestamp(ts_predicao),
        ts_chuva,
    )
    if motivos_stale:
        motivo = "; ".join(motivos_stale)
        LOGGER.error("Inferência cancelada; dados vencidos: %s", motivo)
        for horizonte in MODELOS:
            registrar(
                timestamp=ts_predicao,
                evento_id=evento_id,
                y_pred=None,
                horizonte=horizonte,
                cota_atual=cota_atual,
                ts_observacao=ts_observacao,
                ts_predicao=ts_predicao,
                model_version=MODEL_VERSION,
                stale=True,
            )
        return

    X = calcular_features(df, features)
    features_hash = calcular_features_hash(X)
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
            )
        except Exception as e:
            print(f"[ERRO] Modelo {h} falhou: {e}")
    print(f"[OK] Ciclo sombra concluido. Cota atual: {cota_atual} cm")

if __name__ == "__main__":
    main()
