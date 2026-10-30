import json
import os
import subprocess
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_CHECK = PROJECT_ROOT / "health_check.sh"


def run_health_check(tmp_path, vz_data, rain_mm=0, rain_file=True):
    workspace = tmp_path / "workspace"
    bin_dir = tmp_path / "bin"
    workspace.mkdir()
    bin_dir.mkdir()
    (workspace / "data").mkdir()
    (workspace / "health_check.sh").write_bytes(HEALTH_CHECK.read_bytes())
    (workspace / ".env").write_text(
        "TELEGRAM_TOKEN=test-token\nTELEGRAM_CHAT_ID=test-chat\n",
        encoding="utf-8",
    )
    if rain_file:
        (workspace / "data" / "chuva_montante.csv").write_text(
            "data,chuva_montante_24h\n"
            f"{date.today().isoformat()},{rain_mm}\n",
            encoding="utf-8",
        )

    psql_log = tmp_path / "psql.log"
    curl_log = tmp_path / "curl.log"
    psql = bin_dir / "psql"
    psql.write_text(
        "#!/usr/bin/env bash\n"
        'printf "%s\\n" "$*" >> "$PSQL_LOG"\n'
        'case "$*" in\n'
        '  *localtimestamp*) printf "0\\n" ;;\n'
        '  *"WITH rolling AS"*) printf "%s\\n" "$MOCK_VZ_DATA" ;;\n'
        '  *) printf "NORMAL\\n" ;;\n'
        "esac\n",
        encoding="utf-8",
    )
    curl = bin_dir / "curl"
    curl.write_text(
        "#!/usr/bin/env bash\n"
        'printf "called\\n" >> "$CURL_LOG"\n'
        'printf \'{\"ok\":true}\\n\'\n',
        encoding="utf-8",
    )
    psql.chmod(0o755)
    curl.chmod(0o755)

    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{bin_dir}:{env['PATH']}",
            "PSQL_LOG": str(psql_log),
            "CURL_LOG": str(curl_log),
            "MOCK_VZ_DATA": vz_data,
        }
    )
    result = subprocess.run(
        ["bash", str(workspace / "health_check.sh")],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    return workspace, psql_log.read_text(encoding="utf-8"), curl_log


def test_health_check_alerts_only_after_two_high_smoothed_readings(tmp_path):
    workspace, sql_calls, curl_log = run_health_check(
        tmp_path, "13.50|true|true|false|false"
    )

    result = json.loads((workspace / "data" / "health_check.json").read_text())
    log = (workspace / "logs" / "health_check.log").read_text(encoding="utf-8")

    assert result["status"] == "ALERTA"
    assert result["vz_cm_h"] == 13.5
    assert "Vz suavizado = 13.50 cm/h" in result["mensagem"]
    assert "Vz suavizado (média móvel de 3 leituras): 13.50 cm/h" in log
    assert "alerta de cheia disparado" in log
    assert result["cota_subindo"] is True
    assert result["nivel_alerta"] == "ATENCAO"
    assert "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW" in sql_calls
    assert "LIMIT 2" in sql_calls
    assert "BOOL_AND" in sql_calls
    assert "LAG(cota_cm)" in sql_calls
    assert "LIMIT 4" in sql_calls
    assert curl_log.exists()


def test_health_check_does_not_alert_on_one_high_smoothed_reading(tmp_path):
    workspace, _, curl_log = run_health_check(
        tmp_path, "13.50|true|false|false|false"
    )

    result = json.loads((workspace / "data" / "health_check.json").read_text())
    log = (workspace / "logs" / "health_check.log").read_text(encoding="utf-8")

    assert result["status"] == "OK"
    assert result["vz_cm_h"] == 13.5
    assert not curl_log.exists()
    assert "alerta de cheia não disparado" in log


def test_health_check_does_not_alert_when_level_is_not_rising(tmp_path):
    workspace, _, curl_log = run_health_check(
        tmp_path, "13.50|false|false|false|false"
    )

    result = json.loads((workspace / "data" / "health_check.json").read_text())

    assert result["status"] == "OK"
    assert result["cota_subindo"] is False
    assert not curl_log.exists()


def test_health_check_marks_extreme_persistent_rain_reinforced_alert(tmp_path):
    workspace, _, curl_log = run_health_check(
        tmp_path, "53.20|true|true|true|true", rain_mm=60
    )

    result = json.loads((workspace / "data" / "health_check.json").read_text())
    log = (workspace / "logs" / "health_check.log").read_text(encoding="utf-8")

    assert result["status"] == "ALERTA"
    assert result["nivel_alerta"] == "EXTREMO"
    assert result["alerta_persistente"] is True
    assert "ALERTA REFORÇADO: Vz alto + chuva a montante" in result["mensagem"]
    assert "persistente por mais de 3 leituras consecutivas" in log
    assert curl_log.exists()


def test_health_check_does_not_reinforce_when_rainfall_is_unavailable(tmp_path):
    workspace, _, _ = run_health_check(
        tmp_path, "13.50|true|true|false|false", rain_file=False
    )

    result = json.loads((workspace / "data" / "health_check.json").read_text())

    assert result["status"] == "ALERTA"
    assert result["chuva_montante_24h_mm"] == "N/A"
    assert "ALERTA REFORÇADO" not in result["mensagem"]
