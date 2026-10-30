from src.modelo.ensemble_especialistas import (
    prever_com_fallback,
    rotear_especialista,
)


def test_routes_rapid_and_gradual_events_by_vz_threshold():
    assert rotear_especialista(50.01, 4) == "relampago"
    assert rotear_especialista(50, 4) == "gradual"
    assert rotear_especialista(12, 4) == "gradual"


def test_routes_seasonal_events_when_rise_is_below_threshold():
    assert rotear_especialista(11.9, 6) == "inverno"
    assert rotear_especialista(0, 3) == "verao"
    assert rotear_especialista(0, 4) is None


def test_inactive_expert_falls_back_to_vz_az():
    result = prever_com_fallback(
        {
            "cota": 100,
            "delta_60m": 14,
            "aceleracao_1h": 2,
            "mes": 4,
        },
        registry={},
    )

    assert result == {
        "cota_prevista": 115,
        "especialista": None,
        "metodo": "vz_az",
    }


def test_seasonal_expert_falls_back_when_loeo_does_not_activate_it():
    result = prever_com_fallback(
        {
            "cota": 100,
            "delta_60m": 0,
            "aceleracao_1h": 0,
            "mes": 7,
        },
        registry={"inverno": {"status": "FALLBACK"}},
    )

    assert result["metodo"] == "vz_az"
    assert result["cota_prevista"] == 100


def test_activated_specialist_loads_saved_model(tmp_path):
    import lightgbm as lgb
    import numpy as np
    import pandas as pd

    model_path = tmp_path / "inverno.txt"
    train = lgb.Dataset(
        pd.DataFrame({"cota": [0.0, 1.0, 2.0], "mes": [7.0, 7.0, 7.0]}),
        label=[1.0, 2.0, 3.0],
    )
    model = lgb.train(
        {
            "objective": "regression",
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
            "cota": 100,
            "delta_60m": 0,
            "aceleracao_1h": 0,
            "mes": 7,
            "cota_lag_60m": 100,
        },
        registry={
            "inverno": {
                "status": "ACTIVE",
                "arquivo": model_path.name,
                "features": ["cota", "cota_lag_60m"],
            }
        },
        model_dir=tmp_path,
    )

    assert result["metodo"] == "lightgbm"
    assert result["especialista"] == "inverno"
    assert np.isfinite(result["cota_prevista"])
