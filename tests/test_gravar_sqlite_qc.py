import sqlite3
import tempfile
import unittest
from pathlib import Path

from src.relatorios.gravar_sqlite import gravar_leitura


class GravarSqliteQCTests(unittest.TestCase):
    def test_adds_qc_column_and_keeps_suspect_measurement(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "arcturus.db"
            connection = sqlite3.connect(db_path)
            connection.execute("""
                CREATE TABLE leituras (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    cota_cm REAL,
                    vz_cm_h REAL,
                    az_cm_h2 REAL,
                    regime TEXT
                )
            """)
            connection.execute(
                "INSERT INTO leituras (timestamp, cota_cm) VALUES (?, ?)",
                ("2026-10-27T00:00:00", 80.0),
            )
            connection.commit()
            connection.close()

            qc = gravar_leitura(
                db_path,
                {"delta_60m": 1.0, "aceleracao_az": 0.1, "regime": "NORMAL"},
                {"cota_cm": 111.0, "qc": "VALIDO"},
            )

            connection = sqlite3.connect(db_path)
            columns = {
                row[1] for row in connection.execute("PRAGMA table_info(leituras)")
            }
            rows = connection.execute(
                "SELECT cota_cm, qc FROM leituras ORDER BY id"
            ).fetchall()
            connection.close()

        self.assertIn("qc", columns)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0], (80.0, "VALIDO"))
        self.assertEqual(rows[-1], (111.0, "SUSPEITO"))
        self.assertEqual(qc, "SUSPEITO")

    def test_manual_flag_is_preserved(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "arcturus.db"
            qc = gravar_leitura(
                db_path,
                {},
                {"cota_cm": 90.0, "qc": "MANUAL"},
            )
        self.assertEqual(qc, "MANUAL")


if __name__ == "__main__":
    unittest.main()
