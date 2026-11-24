#!/usr/bin/env python3
"""
ARCTURUS_CLIMATIK — Executor em Modo Sombra do Modelo v11c + Núcleo Físico 3 Braços
Roda em paralelo (silencioso, sem afetar produção ou boletim),
registra predição t+24h (legado v11c) e projeções t+6h / t+12h (núcleo físico regularizado
com separação dos 3 braços + contorno de jusante Laguna).
"""

import json
import pickle
import sys
from datetime import datetime
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.modelo.features_v11c_fisica import calcular_features_v11c_fisica
from src.relatorios.postgres_db import get_postgres_connection

DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models" / "v11c"
LOG_SOMBRA = BASE_DIR / "logs" / "sombra_v11c.jsonl"
LOG_SOMBRA.parent.mkdir(parents=True, exist_ok=True)

COLS_BASE_FISICA = ["cota_cm", "vz_cm_h", "az_cm_h2", "chuva_pior_caso_mm"]
COLS_ENXUTO_3BRACOS = COLS_BASE_FISICA + [
    "oeste_chuva_6h",
    "norte_chuva_6h",
    "oeste_lag_10h",
    "norte_lag_7h",
]


def obter_cota_atual_banco_ou_parquet(df_base: pd.DataFrame) -> float:
    """Tenta ler a cota mais recente do PostgreSQL (em cm); fallback para última linha do parquet."""
    try:
        conn = get_postgres_connection()
        cur = conn.cursor()
        cur.execute("SELECT cota_cm FROM leituras WHERE qc = 'VALIDO' ORDER BY timestamp DESC LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0] is not None:
            return float(row[0])
    except Exception:
        pass
    return float(df_base["ana_cota_m"].iloc[-1])


def carregar_previsao_tripla_hoje() -> dict:
    """Agrega as próximas 24h/48h/72h do previsao_chuva_tripla.csv."""
    arq_prev = DATA_DIR / "previsao_chuva_tripla.csv"
    df_prev = pd.read_csv(arq_prev)
    df_prev["timestamp"] = pd.to_datetime(df_prev["timestamp"])
    df_prev = df_prev.sort_values("timestamp")

    p24 = df_prev.iloc[:24]
    p48 = df_prev.iloc[:48]
    p72 = df_prev.iloc[:72]

    return {
        "prev_chuva_24h_media_mm": float(p24["chuva_media_mm"].sum()),
        "prev_chuva_48h_acum_mm": float(p48["chuva_media_mm"].sum()),
        "prev_chuva_72h_acum_mm": float(p72["chuva_media_mm"].sum()),
        "prev_chuva_24h_pior_caso_mm": float(p24["chuva_pior_caso_mm"].sum()),
        "div_modelos_mm": float(p24["div_horaria"].sum()),
    }


def classificar_confianca_previsao(div_modelos_mm: float, chuva_24h: float) -> str:
    """Define o limite operacional baseado na divergência entre ECMWF, GFS e UKMO."""
    if div_modelos_mm >= 15.0 or (chuva_24h > 10.0 and div_modelos_mm / max(chuva_24h, 1.0) > 0.40):
        return "BAIXA_CONFIANCA_DIVERGENCIA_ALTA"
    if div_modelos_mm >= 6.0:
        return "MEDIA_CONFIANCA"
    return "ALTA_CONFIANCA"


def rodar_nucleo_fisico_3bracos(agora: datetime, cota_atual: float) -> dict:
    """
    Calcula o vetor físico (3 braços + contorno jusante Laguna) e gera projeções
    regularizadas em +6h e +12h sobre a série horária real do PostgreSQL.
    """
    feats_agora = calcular_features_v11c_fisica(agora)
    resultado = {
        "status": "INDISPONIVEL",
        "oeste_chuva_6h_mm": round(float(feats_agora.get("oeste_chuva_6h") or 0.0), 2),
        "norte_chuva_6h_mm": round(float(feats_agora.get("norte_chuva_6h") or 0.0), 2),
        "planicie_dcsc_24h_mm": round(float(feats_agora.get("planicie_dcsc_24h") or 0.0), 2),
        "jusante_mare_msl_m": feats_agora.get("jusante_mare_msl_m"),
        "jusante_vento_sul_kmh": feats_agora.get("jusante_vento_sul_kmh"),
        "indice_bloqueio_foz": feats_agora.get("indice_bloqueio_foz"),
    }

    conn = None
    try:
        conn = get_postgres_connection()
        df = pd.read_sql(
            """
            SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, chuva_pior_caso_mm
            FROM leituras
            WHERE qc = 'VALIDO' AND cota_cm IS NOT NULL
            ORDER BY timestamp ASC;
            """,
            conn,
        )
    except Exception:
        return resultado
    finally:
        if conn is not None:
            conn.close()

    if df.empty or len(df) < 80:
        return resultado

    df["ts"] = pd.to_datetime(df["timestamp"], utc=True).dt.tz_convert("America/Sao_Paulo").dt.tz_localize(None)
    df = df.set_index("ts").resample("1h").agg({
        "cota_cm": "last",
        "vz_cm_h": "last",
        "az_cm_h2": "last",
        "chuva_pior_caso_mm": "max",
    }).dropna(subset=["cota_cm"])

    hist_fis = pd.DataFrame([calcular_features_v11c_fisica(ts) for ts in df.index], index=df.index)
    full = pd.concat([df, hist_fis[["oeste_chuva_6h", "norte_chuva_6h", "oeste_lag_10h", "norte_lag_7h"]]], axis=1)

    ultima_obs = full.iloc[[-1]][COLS_BASE_FISICA].copy()
    ultima_obs["cota_cm"] = cota_atual
    for col in ["oeste_chuva_6h", "norte_chuva_6h", "oeste_lag_10h", "norte_lag_7h"]:
        ultima_obs[col] = feats_agora.get(col)

    for h in (6, 12):
        alvo_col = f"target_delta_{h}h"
        full[alvo_col] = full["cota_cm"].shift(-h) - full["cota_cm"]
        treino = full.dropna(subset=[alvo_col] + COLS_ENXUTO_3BRACOS)
        if len(treino) < 60:
            continue

        modelo_fis = lgb.LGBMRegressor(
            n_estimators=60,
            learning_rate=0.04,
            num_leaves=7,
            min_child_samples=20,
            reg_alpha=5.0,
            reg_lambda=10.0,
            random_state=42,
            verbose=-1,
        )
        modelo_fis.fit(treino[COLS_ENXUTO_3BRACOS], treino[alvo_col])
        delta_h = float(modelo_fis.predict(ultima_obs[COLS_ENXUTO_3BRACOS])[0])
        resultado[f"delta_pred_{h}h_cm"] = round(delta_h, 2)
        resultado[f"cota_prevista_{h}h_cm"] = round(cota_atual + delta_h, 2)

    if "delta_pred_6h_cm" in resultado:
        resultado["status"] = "ATIVO_3BRACOS_JUSANTE"

    return resultado


def main():
    manifesto = json.loads((MODEL_DIR / "manifesto_v11c.json").read_text(encoding="utf-8"))
    features = manifesto["features"]
    stats_ana = manifesto["climatologia_ana"]

    with open(MODEL_DIR / "modelo_v11c_lgbm.pkl", "rb") as f:
        modelo = pickle.load(f)

    df_base = pd.read_parquet(DATA_DIR / "dataset_treino_ana_preparado.parquet").sort_index()
    ultima_linha = df_base.iloc[[-1]].copy()

    cols_chuva_base = [
        c for c in df_base.columns
        if c.startswith("openmeteo_chuva_") and c.endswith("_mm") and "_lag" not in c
    ]
    ultima_linha["bacia_chuva_media_mm"] = ultima_linha[cols_chuva_base].mean(axis=1)
    ultima_linha["bacia_chuva_max_mm"] = ultima_linha[cols_chuva_base].max(axis=1)

    cota_atual = obter_cota_atual_banco_ou_parquet(df_base)
    ultima_linha["ana_cota_m"] = cota_atual
    ultima_linha["cota_norm_p90"] = cota_atual / max(stats_ana["p90"], 0.1)

    agora = datetime.now()
    ultima_linha["mes_sin"] = np.sin(2 * np.pi * agora.month / 12.0)
    ultima_linha["mes_cos"] = np.cos(2 * np.pi * agora.month / 12.0)

    prev = carregar_previsao_tripla_hoje()
    for k, v in prev.items():
        ultima_linha[k] = v

    for col in features:
        if col not in ultima_linha.columns:
            ultima_linha[col] = 0.0

    X_inf = ultima_linha[features]
    delta_pred = float(modelo.predict(X_inf)[0])
    cota_prevista_24h = round(cota_atual + delta_pred, 2)
    confianca = classificar_confianca_previsao(prev["div_modelos_mm"], prev["prev_chuva_24h_media_mm"])

    sombra_fisica = rodar_nucleo_fisico_3bracos(agora, cota_atual)

    registro = {
        "timestamp": agora.isoformat(timespec="seconds"),
        "modelo": "v11c_shadow",
        "cota_atual_cm": round(cota_atual, 2),
        "delta_pred_24h_cm": round(delta_pred, 2),
        "cota_prevista_24h_cm": cota_prevista_24h,
        "prev_chuva_24h_media_mm": round(prev["prev_chuva_24h_media_mm"], 2),
        "prev_chuva_24h_pior_caso_mm": round(prev["prev_chuva_24h_pior_caso_mm"], 2),
        "div_modelos_mm": round(prev["div_modelos_mm"], 2),
        "confianca_operacional": confianca,
        "sombra_fisica_3bracos": sombra_fisica,
    }

    with open(LOG_SOMBRA, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    print(
        f"[SOMBRA v11c] Cota={registro['cota_atual_cm']}cm -> "
        f"Prev24h={registro['cota_prevista_24h_cm']}cm ({registro['delta_pred_24h_cm']:+.2f}cm) | "
        f"Fisica+6h={sombra_fisica.get('cota_prevista_6h_cm')}cm ({sombra_fisica.get('delta_pred_6h_cm', 0):+.2f}cm) | "
        f"Fisica+12h={sombra_fisica.get('cota_prevista_12h_cm')}cm ({sombra_fisica.get('delta_pred_12h_cm', 0):+.2f}cm) | "
        f"BloqueioFoz={sombra_fisica.get('indice_bloqueio_foz')} [{confianca}]"
    )


if __name__ == "__main__":
    main()
