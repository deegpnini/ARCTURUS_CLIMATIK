import logging

import pandas as pd

import src.modelo.features_bacia as features_bacia


def test_future_rainfall_rows_are_logged_and_excluded(tmp_path, monkeypatch, caplog):
    rainfall_path = tmp_path / "rainfall.csv"
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-10-31 09:00:00", periods=5, freq="h"),
            "station_a": [1.0, 2.0, 3.0, 4.0, 1000.0],
            "station_b": [1.0, 2.0, 3.0, 4.0, 1000.0],
        }
    ).to_csv(rainfall_path, index=False)
    monkeypatch.setattr(features_bacia, "ARQUIVO_BACIA", rainfall_path)

    with caplog.at_level(logging.WARNING):
        result = features_bacia.calcular_features_bacia(
            pd.Timestamp("2026-10-31 12:00:00")
        )

    assert result["bacia_3h"] == 9.0
    assert "Possível leakage na chuva" in caplog.text
    assert "linhas futuras serão ignoradas" in caplog.text


def test_nan_rainfall_is_reported_without_replacing_with_zero(
    tmp_path, monkeypatch, caplog
):
    rainfall_path = tmp_path / "rainfall.csv"
    pd.DataFrame(
        {
            "timestamp": pd.date_range("2026-10-31 09:00:00", periods=4, freq="h"),
            "station_a": [1.0, float("nan"), 3.0, 4.0],
            "station_b": [1.0, float("nan"), 3.0, 4.0],
        }
    ).to_csv(rainfall_path, index=False)
    monkeypatch.setattr(features_bacia, "ARQUIVO_BACIA", rainfall_path)

    with caplog.at_level(logging.WARNING):
        result = features_bacia.calcular_features_bacia(
            pd.Timestamp("2026-10-31 12:00:00")
        )

    assert pd.isna(result["bacia_3h"])
    assert "contém 2 valores NaN" in caplog.text
    assert "não serão convertidos em zero" in caplog.text
