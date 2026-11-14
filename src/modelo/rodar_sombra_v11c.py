#!/usr/bin/env python3
"""
ARCTURUS_CLIMATIK — Executor em Modo Sombra do Modelo v11c
Roda em paralelo (silencioso, sem afetar produção ou boletim),
registra predição t+24h e classifica a confiança pelo div_modelos_mm.
"""

import json
import pickle
from datetime import datetime
from pathlib import Path

import numpy as np
import pandas as pd

BASE_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models" / "v11c"
LOG_SOMBRA = BASE_DIR / "logs" / "sombra_v11c.jsonl"
LOG_SOMBRA.parent.mkdir(parents=True, exist_ok=True)


def obter_cota_atual_banco_ou_parquet(df_base: pd.DataFrame) -> float:
    """Tenta ler a cota mais recente do PostgreSQL (em metros); fallback para última linha do parquet."""
    try:
        import psycopg2
        conn = psycopg2.connect(dbname="arcturus")
        cur = conn.cursor()
        cur.execute("SELECT cota_cm FROM leituras WHERE qc = 'VALIDO' ORDER BY timestamp DESC LIMIT 1;")
        row = cur.fetchone()
        cur.close()
        conn.close()
        if row and row[0] is not None:
            # No parquet da ANA, ana_cota_m está na mesma escala numérica (cm no histórico local)
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

    # Garante todas as colunas na ordem exata do treino
    for col in features:
        if col not in ultima_linha.columns:
            ultima_linha[col] = 0.0

    X_inf = ultima_linha[features]
    delta_pred = float(modelo.predict(X_inf)[0])
    cota_prevista_24h = round(cota_atual + delta_pred, 2)
    confianca = classificar_confianca_previsao(prev["div_modelos_mm"], prev["prev_chuva_24h_media_mm"])

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
    }

    with open(LOG_SOMBRA, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    print(
        f"[SOMBRA v11c] Cota={registro['cota_atual_cm']}cm -> "
        f"Prev24h={registro['cota_prevista_24h_cm']}cm ({registro['delta_pred_24h_cm']:+.2f}cm) | "
        f"Chuva24h={registro['prev_chuva_24h_media_mm']}mm | "
        f"Div={registro['div_modelos_mm']}mm [{confianca}]"
    )


if __name__ == "__main__":
    main()
