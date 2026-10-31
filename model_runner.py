#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Motor do modo sombra (v1) — LightGBM v2 regressao (delta de cota).
Usa features disponiveis no PostgreSQL; features de lag/bacia ficam NaN.
Roda no cron a cada 15 min, persiste y_pred, NUNCA dispara alerta.
"""
import json
import math
from datetime import datetime

import lightgbm as lgb
import pandas as pd

from src.relatorios.postgres_db import get_postgres_connection
from persistir_shadow import registrar

# --- CONFIG ---
MANIFESTO = "modelos/manifesto_v8.json"
MODELOS = {
    "1h": "modelos/modelo_delta_1h_v8_final.txt",
    "3h": "modelos/modelo_delta_3h_v8_final.txt",
    "6h": "modelos/modelo_delta_6h_v8_final.txt",
}

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
    """Calcula as features que dao para derivar do historico.
    Features de lag/bacia nao disponiveis ficam NaN."""
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
    # Restantes ficam NaN
    row = {f: base.get(f, float("nan")) for f in features}
    return pd.DataFrame([row])[features]

def main():
    features = carregar_features()
    df = puxar_leituras()
    if df is None or len(df) == 0:
        print("[AVISO] Sem leituras no PostgreSQL. Nada a fazer.")
        return
    X = calcular_features(df, features)
    ts = datetime.now().isoformat()
    evento_id = f"cron_{datetime.now().strftime('%Y%m%d_%H%M')}"
    cota_atual = float(df.iloc[-1]["cota_cm"])
    for h, path in MODELOS.items():
        try:
            modelo = lgb.Booster(model_file=path)
            y_pred = float(modelo.predict(X)[0])
            registrar(
                timestamp=ts,
                evento_id=evento_id,
                y_pred=y_pred,
                horizonte=h,
                cota_atual=cota_atual,
            )
        except Exception as e:
            print(f"[ERRO] Modelo {h} falhou: {e}")
    print(f"[OK] Ciclo sombra concluido. Cota atual: {cota_atual} cm")

if __name__ == "__main__":
    main()
