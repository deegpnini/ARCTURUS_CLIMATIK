import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.relatorios import monitor_continuo


class MonitorQCTests(unittest.TestCase):
    def test_new_history_rows_are_marked_valid(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            results = base / "resultados"
            results.mkdir()
            (base / "tubarao_saneamento_dados.json").write_text(
                json.dumps({"cota_cm": 72.0}),
                encoding="utf-8",
            )
            history = results / "historico_previsoes.csv"

            with (
                patch.object(monitor_continuo, "BASE", base),
                patch.object(monitor_continuo, "HISTORICO", history),
            ):
                qc = monitor_continuo.salvar_no_historico()

            saved = pd.read_csv(history)
            self.assertEqual(qc, "VALIDO")
            self.assertEqual(saved.loc[0, "qc"], "VALIDO")
            self.assertEqual(saved.loc[0, "cota_atual_cm"], 72.0)

    def test_abrupt_jump_is_retained_and_marked_suspect(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            base = Path(temp_dir)
            results = base / "resultados"
            results.mkdir()
            history = results / "historico_previsoes.csv"
            pd.DataFrame(
                [{"timestamp_execucao": "2026-10-27T00:00:00", "cota_atual_cm": 80,
                  "cota_1h_cm": None, "delta_1h_cm": None, "cota_3h_cm": None,
                  "delta_3h_cm": None, "cota_6h_cm": None, "delta_6h_cm": None,
                  "qc": "VALIDO"}]
            ).to_csv(history, index=False)
            (base / "tubarao_saneamento_dados.json").write_text(
                json.dumps({"cota_cm": 111.0}),
                encoding="utf-8",
            )

            with (
                patch.object(monitor_continuo, "BASE", base),
                patch.object(monitor_continuo, "HISTORICO", history),
            ):
                qc = monitor_continuo.salvar_no_historico()

            saved = pd.read_csv(history)
            self.assertEqual(qc, "SUSPEITO")
            self.assertEqual(saved.loc[1, "qc"], "SUSPEITO")
            self.assertEqual(saved.loc[1, "cota_atual_cm"], 111.0)

    def test_invalid_manual_and_corrupt_qc_states(self):
        self.assertEqual(monitor_continuo.determinar_qc(None), "CORROMPIDO")
        self.assertEqual(
            monitor_continuo.determinar_qc(100, 50),
            "SUSPEITO",
        )
        self.assertEqual(
            monitor_continuo.determinar_qc(100, 99),
            "VALIDO",
        )
        self.assertEqual(
            monitor_continuo.determinar_qc(100, 99, "MANUAL"),
            "MANUAL",
        )
        self.assertEqual(
            monitor_continuo.determinar_qc(None, qc_existente="CORROMPIDO"),
            "CORROMPIDO",
        )


if __name__ == "__main__":
    unittest.main()
