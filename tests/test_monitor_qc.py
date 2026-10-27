import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from src.relatorios import monitor_continuo


class MonitorQCTests(unittest.TestCase):
    def test_new_history_rows_default_to_ok(self):
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
                monitor_continuo.salvar_no_historico()

            saved = pd.read_csv(history)
            self.assertEqual(saved.loc[0, "qc"], "ok")
            self.assertEqual(saved.loc[0, "cota_atual_cm"], 72.0)


if __name__ == "__main__":
    unittest.main()
