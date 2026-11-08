#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill com merge_asof por tempo (sem shift, sem nearest_cota)."""

import logging
from datetime import timedelta
from pathlib import Path
import sys
import pandas as pd

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.relatorios.postgres_db import get_postgres_connection

LOG = logging.getLogger("backfill_y_true")
HORIZONS = {"1h": timedelta(hours=1), "3h": timedelta(hours=3), "6h": timedelta(hours=6)}
TOLERANCE = pd.Timedelta(minutes=8)  # Tolerância para o merge_asof


def backfill(connection_factory=get_postgres_connection):
    """Preenche y_true com merge_asof (tolerância de 8 min)."""
    connection = connection_factory()
    updated = 0
    try:
        with connection.cursor() as cursor:
            # 1. Puxa as leituras válidas (com timestamp)
            cursor.execute("""
                SELECT timestamp, cota_cm
                FROM leituras
                WHERE cota_cm IS NOT NULL AND qc = 'VALIDO'
                ORDER BY timestamp
            """)
            rows = cursor.fetchall()
            if not rows:
                LOG.warning("Sem leituras VALIDO no banco.")
                return 0
            df_leituras = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
            df_leituras["timestamp"] = pd.to_datetime(df_leituras["timestamp"])
            df_leituras = df_leituras.sort_values("timestamp").reset_index(drop=True)

            # 2. Puxa as predições sem y_true
            cursor.execute("""
                SELECT id, timestamp, horizonte
                FROM predicoes_shadow
                WHERE y_true IS NULL
                ORDER BY timestamp
            """)
            pendentes = cursor.fetchall()
            LOG.info("Predições sem y_true: %d", len(pendentes))

            # 3. Para cada horizonte, faz o merge_asof
            for h_nome, h_delta in HORIZONS.items():
                pred_h = [(pid, ts) for pid, ts, h in pendentes if h == h_nome]
                if not pred_h:
                    continue

                df_pred = pd.DataFrame(pred_h, columns=["id", "timestamp_origem"])
                df_pred["timestamp_origem"] = pd.to_datetime(df_pred["timestamp_origem"])

                # Merge 1: cota_atual (origem)
                merge_atual = pd.merge_asof(
                    df_pred.sort_values("timestamp_origem"),
                    df_leituras.rename(columns={"timestamp": "timestamp_origem", "cota_cm": "cota_atual"}),
                    on="timestamp_origem", direction="nearest", tolerance=TOLERANCE,
                )

                # Merge 2: cota_futura (origem + horizonte)
                merge_atual["timestamp_alvo"] = merge_atual["timestamp_origem"] + h_delta
                merge_futuro = pd.merge_asof(
                    merge_atual.sort_values("timestamp_alvo"),
                    df_leituras.rename(columns={"timestamp": "timestamp_alvo", "cota_cm": "cota_futura"}),
                    on="timestamp_alvo", direction="nearest", tolerance=TOLERANCE,
                )

                # Calcula o y_true e atualiza
                merge_futuro["y_true"] = merge_futuro["cota_futura"] - merge_futuro["cota_atual"]
                validos = merge_futuro.dropna(subset=["y_true"])

                for _, row in validos.iterrows():
                    cursor.execute(
                        "UPDATE predicoes_shadow SET y_true = %s WHERE id = %s AND y_true IS NULL",
                        (float(row["y_true"]), int(row["id"])),
                    )
                    updated += 1

            connection.commit()
            LOG.info("Backfill concluído: %d linha(s) atualizada(s)", updated)
    except Exception:
        connection.rollback()
        LOG.exception("Falha no backfill")
        raise
    finally:
        connection.close()
    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    backfill()
