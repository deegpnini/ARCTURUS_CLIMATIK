#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill auditado: origem causal (backward), tolerancia rigida e exclusao de stale/invalidos."""

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
TOLERANCE_ORIGEM = pd.Timedelta(minutes=15)
TOLERANCE_ALVO = pd.Timedelta(minutes=8)


def backfill(connection_factory=get_postgres_connection):
    connection = connection_factory()
    updated = 0
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT timestamp, cota_cm
                FROM leituras
                WHERE cota_cm IS NOT NULL AND qc = 'VALIDO'
                ORDER BY timestamp
            """)
            rows = cursor.fetchall()
            if not rows:
                return 0
            df_leituras = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
            df_leituras["timestamp"] = pd.to_datetime(df_leituras["timestamp"])
            df_leituras = df_leituras.sort_values("timestamp").reset_index(drop=True)

            cursor.execute("""
                SELECT id, COALESCE(ts_predicao, timestamp) AS ts_emissao, horizonte
                FROM predicoes_shadow
                WHERE y_true IS NULL
                  AND stale = false
                  AND valido = true
                  AND y_score IS NOT NULL
                ORDER BY ts_emissao
            """)
            pendentes = cursor.fetchall()
            LOG.info("Predições elegíveis sem y_true: %d", len(pendentes))

            for h_nome, h_delta in HORIZONS.items():
                pred_h = [(pid, ts) for pid, ts, h in pendentes if h == h_nome]
                if not pred_h:
                    continue

                df_pred = pd.DataFrame(pred_h, columns=["id", "timestamp_origem"])
                df_pred["timestamp_origem"] = pd.to_datetime(df_pred["timestamp_origem"])

                merge_atual = pd.merge_asof(
                    df_pred.sort_values("timestamp_origem"),
                    df_leituras.rename(columns={"timestamp": "ts_leitura_origem", "cota_cm": "cota_atual"}),
                    left_on="timestamp_origem",
                    right_on="ts_leitura_origem",
                    direction="backward",
                    tolerance=TOLERANCE_ORIGEM,
                )

                merge_atual["timestamp_alvo"] = merge_atual["timestamp_origem"] + h_delta
                merge_futuro = pd.merge_asof(
                    merge_atual.sort_values("timestamp_alvo"),
                    df_leituras.rename(columns={"timestamp": "ts_leitura_alvo", "cota_cm": "cota_futura"}),
                    left_on="timestamp_alvo",
                    right_on="ts_leitura_alvo",
                    direction="nearest",
                    tolerance=TOLERANCE_ALVO,
                )

                merge_futuro["y_true"] = merge_futuro["cota_futura"] - merge_futuro["cota_atual"]
                merge_futuro["desvio_origem_min"] = (
                    (merge_futuro["timestamp_origem"] - merge_futuro["ts_leitura_origem"]).dt.total_seconds() / 60.0
                )
                merge_futuro["desvio_alvo_min"] = (
                    (merge_futuro["ts_leitura_alvo"] - merge_futuro["timestamp_alvo"]).dt.total_seconds() / 60.0
                )

                validos = merge_futuro.dropna(subset=["y_true", "ts_leitura_origem", "ts_leitura_alvo"])

                for _, row in validos.iterrows():
                    cursor.execute(
                        """
                        UPDATE predicoes_shadow
                        SET y_true = %s,
                            ts_leitura_origem = %s,
                            ts_leitura_alvo = %s,
                            desvio_origem_min = %s,
                            desvio_alvo_min = %s
                        WHERE id = %s AND y_true IS NULL
                        """,
                        (
                            float(row["y_true"]),
                            row["ts_leitura_origem"].to_pydatetime(),
                            row["ts_leitura_alvo"].to_pydatetime(),
                            round(float(row["desvio_origem_min"]), 2),
                            round(float(row["desvio_alvo_min"]), 2),
                            int(row["id"]),
                        ),
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
