#!/usr/bin/env python3
"""Compare shadow-model MAE with a zero-delta persistence baseline."""

from collections import defaultdict
from math import fabs

from src.relatorios.postgres_db import get_postgres_connection


def carregar_resultados():
    connection = get_postgres_connection()
    try:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT horizonte, y_true, y_score
                FROM predicoes_shadow
                WHERE y_true IS NOT NULL AND y_score IS NOT NULL
                ORDER BY horizonte, timestamp, id
                """
            )
            return cursor.fetchall()
    finally:
        connection.close()


def calcular_skill_score(rows):
    por_horizonte = defaultdict(list)
    for horizonte, y_true, y_score in rows:
        por_horizonte[horizonte].append((float(y_true), float(y_score)))

    resultados = []
    for horizonte in sorted(por_horizonte, key=lambda valor: (str(valor))):
        amostras = por_horizonte[horizonte]
        mae_modelo = sum(fabs(y_true - y_score) for y_true, y_score in amostras) / len(amostras)
        mae_persistencia = sum(fabs(y_true) for y_true, _ in amostras) / len(amostras)
        skill_score = (
            1 - mae_modelo / mae_persistencia
            if mae_persistencia > 0
            else None
        )
        resultados.append(
            (horizonte, len(amostras), mae_modelo, mae_persistencia, skill_score)
        )
    return resultados


def main():
    resultados = calcular_skill_score(carregar_resultados())
    print("Horizonte | n | MAE_modelo | MAE_persist | Skill_Score")
    print("----------|---|------------|-------------|------------")
    if not resultados:
        print("Sem observações com y_true e y_score.")
        return

    for horizonte, n, mae_modelo, mae_persistencia, skill_score in resultados:
        score_texto = f"{skill_score:.4f}" if skill_score is not None else "N/A"
        print(
            f"{horizonte:<9} | {n:>3} | {mae_modelo:>10.4f} | "
            f"{mae_persistencia:>11.4f} | {score_texto:>11}"
        )


if __name__ == "__main__":
    main()
