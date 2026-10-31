import json
import math
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.relatorios.monitor_continuo import determinar_qc
from src.relatorios.postgres_db import get_postgres_connection


REGIME_FILE = BASE / "data" / "regime_atual.json"
COTA_FILE = BASE / "tubarao_saneamento_dados.json"


def gravar_leitura(regime, dados_cota, connection_factory=get_postgres_connection):
    cota_cm = dados_cota.get("cota_cm")
    qc_fonte = dados_cota.get("qc")
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT cota_cm
                FROM leituras
                WHERE cota_cm IS NOT NULL
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
            """)
            anterior = cursor.fetchone()
            cota_anterior = anterior[0] if anterior else None
            qc = determinar_qc(cota_cm, cota_anterior, qc_fonte)
            if qc == "SUSPEITO":
                print(f"Leitura SUSPEITA ignorada: cota={cota_cm} cm")
                return qc

            if cota_cm is not None:
                try:
                    cota_cm = float(cota_cm)
                except (TypeError, ValueError):
                    cota_cm = None
                    qc = "CORROMPIDO"
                else:
                    if not math.isfinite(cota_cm) or cota_cm <= 0:
                        cota_cm = None
                        qc = "CORROMPIDO"

            cursor.execute("""
                INSERT INTO leituras (
                    timestamp, cota_cm, vz_cm_h, az_cm_h2, regime, qc
                ) VALUES (%s, %s, %s, %s, %s, %s)
            """, (
                datetime.now(),
                cota_cm,
                regime.get("delta_60m"),
                regime.get("aceleracao_az"),
                regime.get("regime", "NORMAL"),
                qc,
            ))
        connection.commit()
        return qc
    finally:
        connection.close()


def main():
    if not REGIME_FILE.exists():
        print("regime_atual.json não encontrado; nenhuma leitura foi gravada.")
        return

    with REGIME_FILE.open("r", encoding="utf-8") as file:
        regime = json.load(file)
    if COTA_FILE.exists():
        with COTA_FILE.open("r", encoding="utf-8") as file:
            dados_cota = json.load(file)
    else:
        dados_cota = {}

    qc = gravar_leitura(regime, dados_cota)
    print(
        "Leitura gravada no PostgreSQL: "
        f"QC={qc}, vz={regime.get('delta_60m')}, "
        f"az={regime.get('aceleracao_az')}, "
        f"regime={regime.get('regime', 'NORMAL')}"
    )


if __name__ == "__main__":
    main()
