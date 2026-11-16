#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extrai o dataset de treino (features + y_true) do PostgreSQL."""

import json
import psycopg2
import pandas as pd
from pathlib import Path

DB_URL = "postgresql:///arcturus"
OUT = Path(__file__).resolve().parent / "data" / "dataset_retreino.parquet"

conn = psycopg2.connect(DB_URL)
cur = conn.cursor()

cur.execute("""
    SELECT
        timestamp,
        horizonte,
        y_true,
        y_score,
        features
    FROM predicoes_shadow
    WHERE y_true IS NOT NULL
      AND features IS NOT NULL
      AND valido IS TRUE
      AND stale IS FALSE
    ORDER BY timestamp
""")

rows = cur.fetchall()
cur.close()
conn.close()

if not rows:
    print("[ERRO] Sem dados para retreino.")
    exit(1)

# Converte para DataFrame
dados = []
for ts, h, y_true, y_score, feat in rows:
    if feat is None:
        continue
    d = json.loads(feat) if isinstance(feat, str) else feat
    d["timestamp"] = ts
    d["horizonte"] = h
    d["y_true"] = y_true
    dados.append(d)

df = pd.DataFrame(dados)
OUT.parent.mkdir(parents=True, exist_ok=True)
df.to_parquet(OUT)
print(f"[OK] Dataset salvo: {OUT} ({len(df)} linhas, {len(df.columns)} colunas)")
print(f"Colunas: {list(df.columns)}")
