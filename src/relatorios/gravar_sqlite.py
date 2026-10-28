import json
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.relatorios.monitor_continuo import determinar_qc


DB_PATH = BASE / "data" / "arcturus.db"
REGIME_FILE = BASE / "data" / "regime_atual.json"
COTA_FILE = BASE / "tubarao_saneamento_dados.json"


def gravar_leitura(db_path, regime, dados_cota):
    cota_cm = dados_cota.get("cota_cm")
    qc_fonte = dados_cota.get("qc")
    connection = sqlite3.connect(db_path)
    try:
        cursor = connection.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS leituras (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                cota_cm REAL,
                vz_cm_h REAL,
                az_cm_h2 REAL,
                regime TEXT,
                chuva_pior_caso_mm REAL,
                confianca_score INTEGER,
                qc TEXT NOT NULL DEFAULT 'VALIDO'
            )
        """)
        columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(leituras)").fetchall()
        }
        if "qc" not in columns:
            cursor.execute("ALTER TABLE leituras ADD COLUMN qc TEXT")

        leituras = cursor.execute(
            "SELECT id, cota_cm, qc FROM leituras ORDER BY id"
        ).fetchall()
        cota_anterior = None
        for leitura_id, cota_existente, qc_existente in leituras:
            qc_atualizado = determinar_qc(
                cota_existente,
                cota_anterior,
                qc_existente,
            )
            if qc_atualizado != qc_existente:
                cursor.execute(
                    "UPDATE leituras SET qc = ? WHERE id = ?",
                    (qc_atualizado, leitura_id),
                )
            if cota_existente is not None:
                try:
                    cota_numerica = float(cota_existente)
                except (TypeError, ValueError):
                    cota_numerica = None
                if (
                    cota_numerica is not None
                    and math.isfinite(cota_numerica)
                    and cota_numerica > 0
                ):
                    cota_anterior = cota_numerica

        anterior = cursor.execute(
            "SELECT cota_cm FROM leituras "
            "WHERE cota_cm IS NOT NULL ORDER BY id DESC LIMIT 1"
        ).fetchone()
        cota_anterior = anterior[0] if anterior else None
        qc = determinar_qc(cota_cm, cota_anterior, qc_fonte)
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
            INSERT INTO leituras (timestamp, cota_cm, vz_cm_h, az_cm_h2, regime, qc)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (
            datetime.now().isoformat(),
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
        print("⚠️ regime_atual.json não encontrado. Nada a gravar.")
        return

    with REGIME_FILE.open("r", encoding="utf-8") as arquivo:
        regime = json.load(arquivo)
    if COTA_FILE.exists():
        with COTA_FILE.open("r", encoding="utf-8") as arquivo:
            dados_cota = json.load(arquivo)
    else:
        dados_cota = {}

    qc = gravar_leitura(DB_PATH, regime, dados_cota)
    print(
        "✅ Leitura gravada no SQLite: "
        f"QC={qc}, vz={regime.get('delta_60m')}, "
        f"az={regime.get('aceleracao_az')}, "
        f"regime={regime.get('regime', 'NORMAL')}"
    )


if __name__ == "__main__":
    main()
