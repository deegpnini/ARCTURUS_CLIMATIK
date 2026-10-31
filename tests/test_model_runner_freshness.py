from datetime import datetime, timedelta
import logging

import pandas as pd

import model_runner


def test_rain_timestamp_uses_latest_row_not_after_observation(tmp_path):
    rainfall_path = tmp_path / "rain.csv"
    pd.DataFrame(
        {"timestamp": pd.date_range("2026-10-31 10:00", periods=4, freq="2h"),
         "rain": [1.0, 2.0, 3.0, 4.0]}
    ).to_csv(rainfall_path, index=False)
    origin = pd.Timestamp("2026-10-31 15:00")

    latest = model_runner.ultima_chuva_observada(origin, rainfall_path)

    assert latest == pd.Timestamp("2026-10-31 14:00")


def test_rain_future_row_emits_leakage_warning(tmp_path, caplog):
    rainfall_path = tmp_path / "rain.csv"
    pd.DataFrame(
        {"timestamp": ["2026-10-31 12:00", "2026-10-31 16:00"],
         "rain": [1.0, 2.0]}
    ).to_csv(rainfall_path, index=False)

    with caplog.at_level(logging.WARNING):
        latest = model_runner.ultima_chuva_observada(
            pd.Timestamp("2026-10-31 14:00"), rainfall_path
        )

    assert latest == pd.Timestamp("2026-10-31 12:00")
    assert "Possível leakage no CSV de chuva" in caplog.text


def test_freshness_guard_flags_old_observation_and_rainfall():
    origin = pd.Timestamp("2026-10-31 12:00")
    prediction = origin + pd.Timedelta(minutes=46)
    rainfall = origin - pd.Timedelta(hours=7)

    reasons = model_runner.motivos_dados_vencidos(origin, prediction, rainfall)

    assert len(reasons) == 2
    assert "leitura com 46.0 min" in reasons[0]
    assert "chuva com 7.0 h" in reasons[1]


def test_stale_data_records_marker_without_running_models(monkeypatch):
    observations = pd.DataFrame(
        {"timestamp": [datetime(2026, 10, 31, 12, 0)], "cota_cm": [70.0]}
    )
    saved = []
    monkeypatch.setattr(model_runner, "carregar_features", lambda: ["cota"])
    monkeypatch.setattr(model_runner, "puxar_leituras", lambda: observations)
    monkeypatch.setattr(
        model_runner,
        "ultima_chuva_observada",
        lambda timestamp: timestamp - pd.Timedelta(hours=7),
    )
    monkeypatch.setattr(
        model_runner,
        "registrar",
        lambda **kwargs: saved.append(kwargs) or True,
    )
    monkeypatch.setattr(
        model_runner.lgb,
        "Booster",
        lambda **kwargs: (_ for _ in ()).throw(AssertionError("model called")),
    )

    model_runner.main()

    assert len(saved) == 3
    assert {row["horizonte"] for row in saved} == {"1h", "3h", "6h"}
    assert all(row["stale"] is True and row["y_pred"] is None for row in saved)
