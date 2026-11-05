#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Backfill point-in-time: recalcula as features para cada linha histórica
(sem vazamento do futuro) e salva um novo dataset.
"""

import json
import sys
from pathlib import Path
from datetime import datetime

import pandas as pd
import numpy as np
import psycopg2

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.modelo.features_bacia import calcular_features_bacia

DB_URL = "postgresql:///arcturus"

def puxar_leituras_ate(conn, ts_alvo, n=200):
    """Puxa leituras até ts_alvo (sem futuro)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2
        FROM leituras
        WHERE cota_cm IS NOT NULL
          AND timestamp <= %s
        ORDER BY timestamp DESC
        LIMIT %s
    """, (ts_alvo, n))
    rows = cur.fetchall()
    cur.close()
    if not rows:
        return None
    cols = ["timestamp", "cota_cm", "vz_cm_h", "az_cm_h2"]
    return pd.DataFrame(rows, columns=cols).sort_values("timestamp").reset_index(drop=True)

def main():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    
    # Puxa as 413 linhas históricas
    cur.execute("""
        SELECT timestamp, horizonte, y_true
        FROM predicoes_shadow
        WHERE y_true IS NOT NULL
          AND valido IS TRUE
          AND stale IS FALSE
        ORDER BY timestamp
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    
    if not rows:
        print("[ERRO] Sem dados para backfill.")
        return
    
    print(f"Total de linhas: {len(rows)}")
    
    novo_dados = []
    for i, (ts, h, y_true) in enumerate(rows):
        if i % 50 == 0:
            print(f"  Processando {i}/{len(rows)}...")
        
        conn2 = psycopg2.connect(DB_URL)
        df = puxar_leituras_ate(conn2, ts)
        conn2.close()
        
        if df is None or len(df) == 0:
            continue
        
        ts = pd.Timestamp(ts)
        ultima = df.iloc[-1]
        cota = float(ultima["cota_cm"])
        vz = ultima["vz_cm_h"]
        az = ultima["az_cm_h2"]
        
        # Recalcula as features de cota (mesma lógica do calcular_features)
        base = {
            "cota": cota,
            "cota_lag_15m": df.iloc[-2]["cota_cm"] if len(df) > 1 else np.nan,
            "cota_lag_30m": df.iloc[-3]["cota_cm"] if len(df) > 2 else np.nan,
            "cota_lag_60m": df.iloc[-5]["cota_cm"] if len(df) > 4 else np.nan,
            "cota_lag_180m": df.iloc[-13]["cota_cm"] if len(df) > 12 else np.nan,
            "cota_lag_360m": df.iloc[-25]["cota_cm"] if len(df) > 24 else np.nan,
            "cota_lag_720m": df.iloc[-49]["cota_cm"] if len(df) > 48 else np.nan,
            "cota_lag_1440m": df.iloc[-97]["cota_cm"] if len(df) > 96 else np.nan,
            "delta_15m": (float(vz) / 4.0) if pd.notna(vz) else np.nan,
            "delta_60m": float(vz) if pd.notna(vz) else np.nan,
            "aceleracao_1h": float(az) if pd.notna(az) else np.nan,
            "sin_hora": np.sin(2 * np.pi * ts.hour / 24),
            "cos_hora": np.cos(2 * np.pi * ts.hour / 24),
            "sin_dia_ano": np.sin(2 * np.pi * ts.dayofyear / 365),
            "cos_dia_ano": np.cos(2 * np.pi * ts.dayofyear / 365),
        }
        
        c3 = base["cota_lag_180m"]
        base["delta_180m"] = (cota - c3) / 3.0 if pd.notna(c3) else np.nan
        
        janela = df.iloc[-48:]["cota_cm"] if len(df) >= 2 else df["cota_cm"]
        base["cota_std_12h"] = float(janela.std()) if len(janela) >= 2 else np.nan
        base["cota_max_12h"] = float(janela.max()) if len(janela) else np.nan
        base["cota_min_12h"] = float(janela.min()) if len(janela) else np.nan
        
        # Recalcula as features de bacia (com os dados até ts)
        base.update(calcular_features_bacia(ts))
        
        base["timestamp"] = ts
        base["horizonte"] = h
        base["y_true"] = y_true
        novo_dados.append(base)
    
    df_novo = pd.DataFrame(novo_dados)
    OUT = BASE / "data" / "dataset_retreino.parquet"
    df_novo.to_parquet(OUT)
    print(f"[OK] Dataset backfill salvo: {OUT} ({len(df_novo)} linhas, {len(df_novo.columns)} colunas)")
    print(f"Colunas: {list(df_novo.columns)}")

if __name__ == "__main__":
    main()
