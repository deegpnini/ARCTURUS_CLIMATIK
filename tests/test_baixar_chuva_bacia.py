import pandas as pd
import pytest

import src.coleta.baixar_chuva_bacia as coleta


def chuva_frame(timestamp, value):
    return pd.DataFrame(
        [{name: value for name in coleta.PONTOS}],
        index=pd.DatetimeIndex([timestamp], name="timestamp"),
    )


def test_csv_update_replaces_file_atomically_and_merges_timestamps(tmp_path):
    csv_path = tmp_path / "rain.csv"
    coleta.atualizar_csv(csv_path, chuva_frame("2026-10-30 10:00:00", 1.0))

    updated = coleta.atualizar_csv(
        csv_path,
        chuva_frame("2026-10-31 10:00:00", 2.0),
    )
    saved = pd.read_csv(csv_path, index_col=0, parse_dates=True)

    assert len(updated) == 2
    assert len(saved) == 2
    assert saved.index.max() == pd.Timestamp("2026-10-31 10:00:00")
    assert list(tmp_path.glob(".rain.csv.*.tmp")) == []


def test_failed_replace_preserves_previous_csv_and_cleans_temporary_file(
    tmp_path, monkeypatch
):
    csv_path = tmp_path / "rain.csv"
    csv_path.write_text("existing data\n", encoding="utf-8")
    original = csv_path.read_bytes()

    def fail_replace(source, destination):
        raise OSError("simulated replace failure")

    monkeypatch.setattr(coleta.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated replace failure"):
        coleta.atualizar_csv(
            csv_path,
            chuva_frame("2026-10-31 10:00:00", 2.0),
        )

    assert csv_path.read_bytes() == original
    assert list(tmp_path.glob(".rain.csv.*.tmp")) == []
