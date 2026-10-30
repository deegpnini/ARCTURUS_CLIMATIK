import pandas as pd
import pytest

from src.modelo.ensemble_especialistas import (
    FEATURES,
    _build_daily_features,
    _identify_events,
    _read_ana,
    prever_com_fallback,
    rotear_especialista,
)


def test_routes_daily_rise_thresholds_and_seasons():
    assert rotear_especialista(50.01, 4) == "relampago"
    assert rotear_especialista(50, 4) == "gradual"
    assert rotear_especialista(12, 4) == "gradual"
    assert rotear_especialista(11.9, 6) == "inverno"
    assert rotear_especialista(0, 3) == "verao"
    assert rotear_especialista(0, 4) is None


def test_training_reader_accepts_only_ana_daily_schema_and_preserves_cm(tmp_path):
    source = tmp_path / "ana.csv"
    source.write_text(
        "Data,Cota (m)\n2020-06-01,250\n2020-06-02,310\n",
        encoding="utf-8",
    )

    series = _read_ana(source)

    assert series["cota_cm"].tolist() == [250, 310]
    with pytest.raises(ValueError, match="série diária da ANA"):
        invalid = tmp_path / "operacional.csv"
        invalid.write_text("timestamp,cota\n2020-06-01,250\n", encoding="utf-8")
        _read_ana(invalid)


def test_identifies_flood_events_and_assigns_rate_and_season_labels():
    index = pd.date_range("2020-06-01", periods=6, freq="D")
    series = pd.DataFrame(
        {"cota_cm": [250, 310, 315, 200, 260, 311]},
        index=index,
    )

    events = _identify_events(series)

    assert len(events) == 2
    assert events[0]["vz_inicio_cm_dia"] == 60
    assert events[0]["labels"] == {"relampago", "inverno"}
    assert events[1]["vz_inicio_cm_dia"] == 51
    assert events[1]["labels"] == {"relampago", "inverno"}


def test_daily_features_use_300_cm_next_day_target():
    index = pd.date_range("2020-01-01", periods=3, freq="D")
    series = pd.DataFrame({"cota_cm": [290, 300, 310]}, index=index)

    features = _build_daily_features(series)

    assert set(FEATURES).issubset(features.columns)
    assert features["target_cheia_d1"].iloc[0] == 1
    assert features["target_cheia_d1"].iloc[1] == 1
    assert pd.isna(features["target_cheia_d1"].iloc[2])


def test_missing_previous_ana_day_does_not_invent_onset_vz():
    index = pd.to_datetime(["2020-06-01", "2020-06-03", "2020-06-04"])
    series = pd.DataFrame({"cota_cm": [290, 310, 320]}, index=index)

    event = _identify_events(series)[0]

    assert event["vz_inicio_cm_dia"] is None
    assert "relampago" not in event["labels"]
    assert "inverno" in event["labels"]


def test_inactive_expert_falls_back_to_daily_vz_az():
    result = prever_com_fallback(
        {
            "cota_cm": 290,
            "vz_1d_cm": 10,
            "az_1d_cm_dia": 4,
            "mes": 4,
        },
        registry={},
    )

    assert result == {
        "probabilidade_cheia_d1": 1.0,
        "especialista": None,
        "metodo": "vz_az",
    }


def test_inactive_seasonal_specialist_falls_back():
    result = prever_com_fallback(
        {
            "cota_cm": 100,
            "vz_1d_cm": 0,
            "az_1d_cm_dia": 0,
            "mes": 7,
        },
        registry={"inverno": {"status": "FALLBACK"}},
    )

    assert result["metodo"] == "vz_az"
    assert result["probabilidade_cheia_d1"] == 0.0


def test_activated_specialist_loads_saved_ana_feature_model(tmp_path):
    import lightgbm as lgb
    import numpy as np

    model_path = tmp_path / "inverno.txt"
    train = lgb.Dataset(
        pd.DataFrame(
            {
                "cota_cm": [290.0, 310.0, 280.0, 320.0],
                "vz_1d_cm": [5.0, 20.0, 4.0, 30.0],
            }
        ),
        label=[0, 1, 0, 1],
    )
    model = lgb.train(
        {
            "objective": "binary",
            "verbosity": -1,
            "num_threads": 1,
            "min_data_in_leaf": 1,
        },
        train,
        num_boost_round=2,
    )
    model.save_model(str(model_path))
    result = prever_com_fallback(
        {
            "cota_cm": 290,
            "vz_1d_cm": 0,
            "az_1d_cm_dia": 2,
            "mes": 7,
        },
        registry={
            "inverno": {
                "status": "ACTIVE",
                "arquivo": model_path.name,
                "features": ["cota_cm", "vz_1d_cm"],
            }
        },
        model_dir=tmp_path,
    )

    assert result["metodo"] == "lightgbm"
    assert result["especialista"] == "inverno"
    assert np.isfinite(result["probabilidade_cheia_d1"])
