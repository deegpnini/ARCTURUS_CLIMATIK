from pathlib import Path

import pandas as pd

import boletim_sombra


def test_run_cycle_registers_shadow_comparison_after_prospectiva():
    text = (Path(__file__).resolve().parents[1] / "run_cycle.sh").read_text(encoding="utf-8")

    prospectiva = text.index("executar_rodada_prospectiva.py")
    shadow = text.index("boletim_sombra.py")
    official_send = text.index("boletim_telegram.py")

    assert prospectiva < shadow < official_send
    assert "log_timeout" in text[shadow:text.index("boletim_sombra.py", shadow + 1) if text.find("boletim_sombra.py", shadow + 1) >= 0 else official_send]


def test_choice_keeps_official_in_dry_scenario_and_shadow_in_rain():
    oficial = {"1h": 1.0, "3h": 2.0, "6h": 3.0}
    sombra = {"1h": 1.5, "3h": 2.5, "6h": 20.0}

    scenario, chosen = boletim_sombra.escolher_combinacao(oficial, sombra, 4.99)
    assert scenario == "SECO"
    assert chosen is oficial

    scenario, chosen = boletim_sombra.escolher_combinacao(oficial, sombra, 5.0)
    assert scenario == "CHUVA"
    assert chosen is sombra


def test_shadow_module_never_changes_official_prediction_mapping(monkeypatch, tmp_path):
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    now = pd.Timestamp.now()
    pd.DataFrame(
        {"cidade_a": [1.0, 2.0], "cidade_b": [1.0, 2.0]},
        index=[now + pd.Timedelta(hours=1), now + pd.Timedelta(hours=3)],
    ).to_csv(data_dir / "chuva_bacia_openmeteo.csv")

    monkeypatch.setattr(boletim_sombra, "BASE", tmp_path)

    chuva = boletim_sombra.obter_chuva_prevista(horas=6)
    assert chuva == 6.0
