import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import src.relatorios.monitor_derivada as monitor
from src.relatorios.monitor_derivada import (
    atualizar_confirmacao,
    az_robusto,
    vz_robusto,
    vz_suavizado_3,
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

    def test_smoothed_vz_averages_the_three_latest_rates(self):
        self.assertAlmostEqual(
            vz_suavizado_3([0, 0.5, 1, 1.5], [10, 11, 12, 14]),
            2.6666666667,
        )

    def test_smoothed_vz_requires_four_readings(self):
        self.assertIsNone(vz_suavizado_3([0, 0.5, 1], [10, 11, 12]))


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

    def test_persistence_is_recorded_after_four_confirmed_cycles(self):
        regime, candidate, count = "NORMAL", None, 0
        previous_timestamp = None
        for index in range(4):
            timestamp = f"2026-10-27T0{index}:00:00"
            regime, candidate, count = atualizar_confirmacao(
                regime,
                candidate,
                count,
                previous_timestamp,
                "EXTREMO",
                timestamp,
            )
            previous_timestamp = timestamp
        self.assertEqual((regime, candidate, count), ("EXTREMO", "EXTREMO", 4))


class MonitorIntegrationTests(unittest.TestCase):
    def test_short_history_keeps_regime_and_stores_null_metrics(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.csv"
            regime_path = root / "regime.json"
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
            ):
                monitor.calcular_derivada()
                state = json.loads(regime_path.read_text(encoding="utf-8"))
                self.assertEqual(state["regime"], "NORMAL")
                self.assertEqual(state["regime_candidato"], "ATENCAO")
                self.assertEqual(state["contador_candidato"], 1)
                self.assertEqual(state["delta_60m"], 40.0)
                self.assertEqual(state["vz_robusto"], 40.0)
                self.assertEqual(state["vz_suavizado"], 40.0)
                self.assertTrue(state["cota_subindo"])
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
            self.assertFalse(state["alerta_persistente"])
            self.assertEqual(
                state["timestamp_ultima_observacao"],
                "2026-10-27T02:00:00",
            )

    def test_high_smoothed_vz_does_not_activate_when_level_is_falling(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.csv"
            regime_path = root / "regime.json"
            rainfall_path = root / "rain.csv"
            timestamps = pd.date_range("2026-10-27T00:00:00", periods=4, freq="30min")
            pd.DataFrame(
                {
                    "timestamp_execucao": timestamps.strftime("%Y-%m-%dT%H:%M:%S"),
                    "cota_atual_cm": [10, 30, 50, 40],
                }
            ).to_csv(history_path, index=False)
            rainfall_path.write_text(
                "data,chuva_montante_24h\n2026-10-27,60\n", encoding="utf-8"
            )

            with (
                patch.object(monitor, "HISTORICO", history_path),
                patch.object(monitor, "REGIME_FILE", regime_path),
                patch.object(monitor, "CHUVA_MONTANTE_FILE", rainfall_path),
            ):
                monitor.calcular_derivada()

            state = json.loads(regime_path.read_text(encoding="utf-8"))
            self.assertEqual(state["vz_suavizado"], 20.0)
            self.assertFalse(state["cota_subindo"])
            self.assertEqual(state["regime_candidato"], "NORMAL")
            self.assertFalse(state["alerta_reforcado"])

    def test_confirmed_rising_vz_is_reinforced_by_upstream_rain(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.csv"
            regime_path = root / "regime.json"
            rainfall_path = root / "rain.csv"
            timestamps = pd.date_range(
                pd.Timestamp.now().floor("min") - pd.Timedelta(hours=2),
                periods=4,
                freq="30min",
            )
            history = pd.DataFrame(
                {
                    "timestamp_execucao": timestamps.strftime("%Y-%m-%dT%H:%M:%S"),
                    "cota_atual_cm": [10, 20, 30, 40],
                }
            )
            history.to_csv(history_path, index=False)
            rainfall_path.write_text(
                f"data,chuva_montante_24h\n{datetime.now():%Y-%m-%d},60\n",
                encoding="utf-8",
            )
            regime_path.write_text(
                json.dumps(
                    {
                        "regime": "NORMAL",
                        "regime_candidato": "ATENCAO",
                        "contador_candidato": 1,
                        "timestamp_ultima_observacao": timestamps[-1].isoformat(),
                    }
                ),
                encoding="utf-8",
            )
            next_timestamp = timestamps[-1] + pd.Timedelta(minutes=30)
            history.loc[len(history)] = [
                next_timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
                50,
            ]
            history.to_csv(history_path, index=False)

            with (
                patch.object(monitor, "HISTORICO", history_path),
                patch.object(monitor, "REGIME_FILE", regime_path),
                patch.object(monitor, "CHUVA_MONTANTE_FILE", rainfall_path),
            ):
                monitor.calcular_derivada()

            state = json.loads(regime_path.read_text(encoding="utf-8"))
            self.assertEqual(state["regime"], "ATENCAO")
            self.assertEqual(state["chuva_montante_24h_mm"], 60.0)
            self.assertTrue(state["alerta_reforcado"])
            self.assertIn("ALERTA REFORÇADO: Vz alto + chuva a montante", state["motivo"])

    def test_extreme_regime_requires_two_rising_cycles_above_52(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            history_path = root / "history.csv"
            regime_path = root / "regime.json"
            timestamps = pd.date_range(
                pd.Timestamp.now().floor("min") - pd.Timedelta(hours=2),
                periods=4,
                freq="30min",
            )
            history = pd.DataFrame(
                {
                    "timestamp_execucao": timestamps.strftime("%Y-%m-%dT%H:%M:%S"),
                    "cota_atual_cm": [10, 40, 70, 100],
                }
            )
            history.to_csv(history_path, index=False)

            with (
                patch.object(monitor, "HISTORICO", history_path),
                patch.object(monitor, "REGIME_FILE", regime_path),
                patch.object(
                    monitor, "CHUVA_MONTANTE_FILE", root / "missing-rain.csv"
                ),
            ):
                monitor.calcular_derivada()
                state = json.loads(regime_path.read_text(encoding="utf-8"))
                self.assertEqual(state["regime"], "INDEFINIDO")
                self.assertEqual(state["contador_candidato"], 1)

                next_timestamp = timestamps[-1] + pd.Timedelta(minutes=30)
                history.loc[len(history)] = [
                    next_timestamp.strftime("%Y-%m-%dT%H:%M:%S"),
                    130,
                ]
                history.to_csv(history_path, index=False)
                monitor.calcular_derivada()
                state = json.loads(regime_path.read_text(encoding="utf-8"))

            self.assertEqual(state["vz_suavizado"], 60.0)
            self.assertEqual(state["regime"], "EXTREMO")
            self.assertEqual(state["regime_candidato"], "EXTREMO")
            self.assertEqual(state["contador_candidato"], 2)


if __name__ == "__main__":
    unittest.main()
