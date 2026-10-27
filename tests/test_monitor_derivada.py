import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import src.relatorios.monitor_derivada as monitor
from src.relatorios.monitor_derivada import (
    atualizar_confirmacao,
    az_robusto,
    vz_robusto,
)


class VzRobustoTests(unittest.TestCase):
    def test_constant_slope(self):
        self.assertAlmostEqual(
            vz_robusto([0, 0.25, 0.5, 0.75], [10, 10.5, 11, 11.5]),
            2.0,
        )

    def test_isolated_outlier_does_not_change_trend(self):
        self.assertAlmostEqual(
            vz_robusto(
                [0, 0.25, 0.5, 0.75, 1],
                [10, 10.5, 50, 11.5, 12],
                n=5,
            ),
            2.0,
        )

    def test_history_shorter_than_thirty_minutes_is_unavailable(self):
        self.assertIsNone(vz_robusto([0, 0.1, 0.25], [10, 10.2, 10.5]))

    def test_duplicate_timestamps_are_deduplicated(self):
        self.assertAlmostEqual(
            vz_robusto([0, 0.25, 0.25, 0.5], [10, 10.5, 10.5, 11]),
            2.0,
        )

    def test_acceleration_uses_rates_separated_by_at_least_thirty_minutes(self):
        self.assertAlmostEqual(
            az_robusto([0, 0.5, 1, 1.5], [10, 11, 12, 13]),
            0.0,
        )

    def test_acceleration_is_unavailable_without_an_older_rate(self):
        self.assertIsNone(az_robusto([0, 0.25, 0.5], [10, 10.5, 11]))


class RegimeConfirmationTests(unittest.TestCase):
    def test_candidate_is_confirmed_on_second_new_cycle(self):
        regime, candidate, count = atualizar_confirmacao(
            "NORMAL", None, 0, None, "ATENCAO", "2026-10-27T00:00:00"
        )
        self.assertEqual((regime, candidate, count), ("NORMAL", "ATENCAO", 1))

        regime, candidate, count = atualizar_confirmacao(
            regime,
            candidate,
            count,
            "2026-10-27T00:00:00",
            "ATENCAO",
            "2026-10-27T00:30:00",
        )
        self.assertEqual((regime, candidate, count), ("ATENCAO", "ATENCAO", 2))

    def test_candidate_change_resets_counter(self):
        regime, candidate, count = atualizar_confirmacao(
            "NORMAL",
            "ATENCAO",
            1,
            "2026-10-27T00:00:00",
            "EXTREMO",
            "2026-10-27T00:30:00",
        )
        self.assertEqual((regime, candidate, count), ("NORMAL", "EXTREMO", 1))

    def test_same_timestamp_does_not_advance_counter(self):
        result = atualizar_confirmacao(
            "NORMAL",
            "ATENCAO",
            1,
            "2026-10-27T00:00:00",
            "ATENCAO",
            "2026-10-27T00:00:00",
        )
        self.assertEqual(result, ("NORMAL", "ATENCAO", 1))


class MonitorIntegrationTests(unittest.TestCase):
    def test_short_history_keeps_regime_and_stores_null_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.csv"
            regime_path = root / "regime.json"
            ensemble_path = root / "ensemble.json"
            pd.DataFrame(
                {
                    "timestamp_execucao": [
                        "2026-10-27T00:00:00",
                        "2026-10-27T00:15:00",
                    ],
                    "cota_atual_cm": [50, 55],
                }
            ).to_csv(history_path, index=False)
            regime_path.write_text(
                json.dumps(
                    {
                        "regime": "ATENCAO",
                        "regime_candidato": "EXTREMO",
                        "contador_candidato": 1,
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(monitor, "HISTORICO", history_path),
                patch.object(monitor, "REGIME_FILE", regime_path),
                patch.object(monitor, "ENSEMBLE_FILE", ensemble_path),
            ):
                monitor.calcular_derivada()

            state = json.loads(regime_path.read_text(encoding="utf-8"))
            self.assertEqual(state["regime"], "ATENCAO")
            self.assertIsNone(state["delta_60m"])
            self.assertIsNone(state["vz_robusto"])
            self.assertIsNone(state["aceleracao_az"])
            self.assertIsNone(state["az_robusto"])
            self.assertIsNone(state["regime_candidato"])
            self.assertEqual(state["contador_candidato"], 0)

    def test_persists_metrics_and_confirms_only_after_two_new_cycles(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.csv"
            regime_path = root / "regime.json"
            ensemble_path = root / "ensemble.json"
            timestamps = pd.date_range("2026-10-27T00:00:00", periods=4, freq="30min")
            history = pd.DataFrame(
                {
                    "timestamp_execucao": timestamps.strftime("%Y-%m-%dT%H:%M:%S"),
                    "cota_atual_cm": [10, 30, 50, 70],
                }
            )
            history.to_csv(history_path, index=False)
            regime_path.write_text(
                json.dumps(
                    {
                        "regime": "NORMAL",
                        "regime_candidato": None,
                        "contador_candidato": 0,
                    }
                ),
                encoding="utf-8",
            )

            with (
                patch.object(monitor, "HISTORICO", history_path),
                patch.object(monitor, "REGIME_FILE", regime_path),
                patch.object(monitor, "ENSEMBLE_FILE", ensemble_path),
            ):
                monitor.calcular_derivada()
                state = json.loads(regime_path.read_text(encoding="utf-8"))
                self.assertEqual(state["regime"], "NORMAL")
                self.assertEqual(state["regime_candidato"], "ATENCAO")
                self.assertEqual(state["contador_candidato"], 1)
                self.assertEqual(state["delta_60m"], 40.0)
                self.assertEqual(state["vz_robusto"], 40.0)
                self.assertEqual(state["az_robusto"], 0.0)

                history.loc[len(history)] = [
                    "2026-10-27T02:00:00",
                    90,
                ]
                history.to_csv(history_path, index=False)
                self.assertEqual(len(pd.read_csv(history_path)), 5)
                self.assertEqual(
                    pd.read_csv(history_path).iloc[-1]["timestamp_execucao"],
                    "2026-10-27T02:00:00",
                )
                monitor.calcular_derivada()
                state = json.loads(regime_path.read_text(encoding="utf-8"))

            self.assertEqual(state["regime"], "ATENCAO", state)
            self.assertEqual(state["regime_candidato"], "ATENCAO")
            self.assertEqual(state["contador_candidato"], 2)
            self.assertEqual(
                state["timestamp_ultima_observacao"],
                "2026-10-27T02:00:00",
            )


if __name__ == "__main__":
    unittest.main()
