#!/usr/bin/env python3
"""Backfill observed cota deltas for shadow predictions."""

import logging
from datetime import timedelta
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.relatorios.postgres_db import get_postgres_connection


LOG = logging.getLogger("backfill_y_true")
HORIZONS = {
    "1h": timedelta(hours=1),
    "3h": timedelta(hours=3),
    "6h": timedelta(hours=6),
}
TOLERANCE = timedelta(minutes=15)


def nearest_cota(cursor, timestamp):
    cursor.execute(
        """
        SELECT cota_cm
        FROM leituras
        WHERE cota_cm IS NOT NULL
          AND timestamp BETWEEN %s AND %s
        ORDER BY ABS(EXTRACT(EPOCH FROM (timestamp - %s))), timestamp DESC
        LIMIT 1
        """,
        (timestamp - TOLERANCE, timestamp + TOLERANCE, timestamp),
    )
    row = cursor.fetchone()
    return row[0] if row else None


def backfill(connection_factory=get_postgres_connection):
    """Fill targets when both prediction-time and future readings are available."""
    connection = connection_factory()
    updated = 0
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT id, timestamp, horizonte
                FROM predicoes_shadow
                WHERE y_true IS NULL
                ORDER BY timestamp, id
                """
            )
            pending_predictions = cursor.fetchall()
            LOG.info("Predições sem y_true encontradas: %d", len(pending_predictions))

            for prediction_id, prediction_timestamp, horizon in pending_predictions:
                delta_horizon = HORIZONS.get(horizon)
                if delta_horizon is None:
                    LOG.warning(
                        "Predição id=%s pendente: horizonte não suportado (%r)",
                        prediction_id,
                        horizon,
                    )
                    continue

                cota_atual = nearest_cota(cursor, prediction_timestamp)
                if cota_atual is None:
                    LOG.debug(
                        "Predição id=%s pendente: sem leitura próxima ao timestamp "
                        "da previsão",
                        prediction_id,
                    )
                    continue

                timestamp_alvo = prediction_timestamp + delta_horizon
                cota_futura = nearest_cota(cursor, timestamp_alvo)
                if cota_futura is None:
                    LOG.debug(
                        "Predição id=%s pendente: sem leitura futura próxima de %s",
                        prediction_id,
                        timestamp_alvo.isoformat(),
                    )
                    continue

                y_true = cota_futura - cota_atual
                cursor.execute(
                    """
                    UPDATE predicoes_shadow
                    SET y_true = %s
                    WHERE id = %s AND y_true IS NULL
                    """,
                    (y_true, prediction_id),
                )
                updated += cursor.rowcount

        connection.commit()
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM predicoes_shadow WHERE y_true IS NULL"
            )
            still_pending = cursor.fetchone()[0]

        LOG.info(
            "Backfill concluído: %d linha(s) atualizada(s); %d linha(s) ainda "
            "pendente(s) no total.",
            updated,
            still_pending,
        )
        return updated, still_pending
    except Exception:
        connection.rollback()
        LOG.exception("Falha ao executar backfill de y_true; transação revertida.")
        raise
    finally:
        connection.close()


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    try:
        backfill()
    except Exception:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
