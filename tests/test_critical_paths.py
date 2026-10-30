import os
import shlex
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, Mock, patch

import app_dash
from src.relatorios import coletar_tubarao_saneamento
from src.relatorios.gravar_postgres import gravar_leitura
from src.relatorios.monitor_continuo import determinar_qc
from src.relatorios.monitor_derivada import az_robusto, vz_robusto


PROJECT_ROOT = Path(__file__).resolve().parents[1]
NYLAS_LAUNCHER = PROJECT_ROOT / ".vscode" / "nylas-mcp.sh"


def test_erab_collector_extracts_cota_from_mocked_html():
    element = Mock()
    element.inner_text.return_value = "0,65"
    page = Mock()
    page.query_selector.return_value = element
    browser = Mock()
    browser.new_page.return_value = page
    playwright = Mock()
    playwright.chromium.launch.return_value = browser
    saved_readings = []

    with (
        patch.object(
            coletar_tubarao_saneamento,
            "sync_playwright",
        ) as sync_playwright,
        patch.object(
            coletar_tubarao_saneamento,
            "salvar_no_historico",
            side_effect=lambda reading: saved_readings.append(reading) or "VALIDO",
        ),
        patch("builtins.open", create=True),
    ):
        sync_playwright.return_value.__enter__.return_value = playwright
        coletar_tubarao_saneamento.coletar_cota()

    page.goto.assert_called_once()
    page.query_selector.assert_called_once_with(".chartjs-value")
    browser.close.assert_called_once()
    assert saved_readings[0]["cota_metros"] == 0.65
    assert saved_readings[0]["cota_cm"] == 65.0
    assert saved_readings[0]["qc"] == "VALIDO"


def test_theil_sen_vz_and_az_for_constant_rise():
    times_hours = [0, 1, 2, 3]
    cota_cm = [65, 66, 67, 68]

    assert vz_robusto(times_hours, cota_cm) == 1.0
    assert az_robusto(times_hours, cota_cm) == 0.0


def test_abrupt_cota_jump_is_marked_suspect():
    assert determinar_qc(cota=111, cota_anterior=80) == "SUSPEITO"


def test_last_alert_card_shows_no_recent_alert_for_ok_health_status():
    with TemporaryDirectory() as temp_dir:
        health_file = Path(temp_dir) / "health_check.json"
        health_file.write_text('{"status": "OK"}', encoding="utf-8")
        with patch.object(app_dash, "FILE_HEALTH", health_file):
            assert app_dash.ler_ultimo_alerta() == "✅ Nenhum alerta recente"


def test_last_alert_card_shows_telegram_alert_and_vz():
    with TemporaryDirectory() as temp_dir:
        health_file = Path(temp_dir) / "health_check.json"
        health_file.write_text(
            '{"status": "ALERTA", "vz_cm_h": 12.5}',
            encoding="utf-8",
        )
        with patch.object(app_dash, "FILE_HEALTH", health_file):
            assert app_dash.ler_ultimo_alerta() == (
                "⚠️ Alerta enviado ao Telegram (Vz = 12.5 cm/h)"
            )


def test_atlas_impact_card_shows_reported_2019_metrics():
    response = app_dash.app.server.test_client().get("/_dash-layout")

    assert response.status_code == 200
    layout = response.get_json()

    def collect_strings(value):
        if isinstance(value, str):
            return [value]
        if isinstance(value, dict):
            return [text for item in value.values() for text in collect_strings(item)]
        if isinstance(value, list):
            return [text for item in value for text in collect_strings(item)]
        return []

    layout_text = " ".join(collect_strings(layout))
    assert "A.C. Atlas — Impacto 2019" in layout_text
    assert "Edificações afetadas: 1.290" in layout_text
    assert "Escolas afetadas: 0" in layout_text
    assert "UBS afetadas: 0" in layout_text
    assert "População estimada: N/D" in layout_text


def test_postgres_writer_uses_mock_connection():
    connection = MagicMock()
    cursor = connection.cursor.return_value.__enter__.return_value
    cursor.fetchone.return_value = None
    connection_factory = Mock(return_value=connection)

    qc = gravar_leitura(
        {"delta_60m": 1.0, "aceleracao_az": 0.0, "regime": "NORMAL"},
        {"cota_cm": 65, "qc": "VALIDO"},
        connection_factory=connection_factory,
    )

    assert qc == "VALIDO"
    connection_factory.assert_called_once_with()
    connection.commit.assert_called_once_with()
    connection.close.assert_called_once_with()
    insert_call = cursor.execute.call_args_list[-1]
    assert "INSERT INTO leituras" in insert_call.args[0]
    assert insert_call.args[1][-1] == "VALIDO"


def test_nylas_launcher_sources_dotenv_without_printing_values():
    assert NYLAS_LAUNCHER.is_file(), "Nylas launcher is not present in this workspace."

    with TemporaryDirectory() as temp_dir:
        workspace = Path(temp_dir)
        fake_binary = workspace / "fake-nylas"
        marker = workspace / "launcher-ran"
        fake_binary.write_text(
            "#!/usr/bin/env bash\n"
            "set -euo pipefail\n"
            "[[ -n \"${NYLAS_API_KEY:-}\" ]]\n"
            "[[ -n \"${NYLAS_GRANT_ID:-}\" ]]\n"
            "[[ -n \"${NYLAS_FILE_STORE_PASSPHRASE:-}\" ]]\n"
            f"printf loaded > {shlex.quote(str(marker))}\n",
            encoding="utf-8",
        )
        fake_binary.chmod(0o755)
        env_file = workspace / ".env"
        env_file.write_text(
            "NYLAS_API_KEY=unit-test-api-key\n"
            "NYLAS_GRANT_ID=unit-test-grant-id\n"
            "NYLAS_FILE_STORE_PASSPHRASE=unit-test-passphrase\n",
            encoding="utf-8",
        )

        launcher_text = NYLAS_LAUNCHER.read_text(encoding="utf-8")
        launcher_text = launcher_text.replace(
            'workspace_root="/home/oikos/projetos/ARCTURUS_CLIMATIK"',
            f"workspace_root={shlex.quote(str(workspace))}",
        )
        launcher_text = launcher_text.replace(
            "exec /home/oikos/.config/nylas/bin/nylas mcp serve",
            f"exec {shlex.quote(str(fake_binary))} mcp serve",
        )
        launcher = workspace / "nylas-mcp.sh"
        launcher.write_text(launcher_text, encoding="utf-8")
        launcher.chmod(0o755)

        clean_env = os.environ.copy()
        for key in (
            "NYLAS_API_KEY",
            "NYLAS_GRANT_ID",
            "NYLAS_FILE_STORE_PASSPHRASE",
        ):
            clean_env.pop(key, None)

        result = subprocess.run(
            ["bash", str(launcher)],
            capture_output=True,
            text=True,
            env=clean_env,
            check=False,
        )

        assert result.returncode == 0, result.stderr
        assert marker.read_text(encoding="utf-8") == "loaded"
        assert "unit-test-api-key" not in result.stdout + result.stderr
        assert "unit-test-grant-id" not in result.stdout + result.stderr
        assert "unit-test-passphrase" not in result.stdout + result.stderr
