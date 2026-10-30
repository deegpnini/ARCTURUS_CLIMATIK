import json
import os
import subprocess
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
HEALTH_CHECK = PROJECT_ROOT / "health_check.sh"


def run_health_check(tmp_path, vz_data):
    workspace = tmp_path / "workspace"
    bin_dir = tmp_path / "bin"
    workspace.mkdir()
    bin_dir.mkdir()
    (workspace / "health_check.sh").write_bytes(HEALTH_CHECK.read_bytes())
    (workspace / ".env").write_text(
        "TELEGRAM_TOKEN=test-token\nTELEGRAM_CHAT_ID=test-chat\n",
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
    workspace, sql_calls, curl_log = run_health_check(tmp_path, "13.50|true")

    result = json.loads((workspace / "data" / "health_check.json").read_text())
    log = (workspace / "logs" / "health_check.log").read_text(encoding="utf-8")

    assert result["status"] == "ALERTA"
    assert result["vz_cm_h"] == 13.5
    assert "Vz suavizado = 13.50 cm/h" in result["mensagem"]
    assert "Vz suavizado (média móvel de 3 leituras): 13.50 cm/h" in log
    assert "alerta de cheia disparado" in log
    assert "ROWS BETWEEN 2 PRECEDING AND CURRENT ROW" in sql_calls
    assert "LIMIT 2" in sql_calls
    assert "BOOL_AND" in sql_calls
    assert curl_log.exists()


def test_health_check_does_not_alert_on_one_high_smoothed_reading(tmp_path):
    workspace, _, curl_log = run_health_check(tmp_path, "13.50|false")

    result = json.loads((workspace / "data" / "health_check.json").read_text())
    log = (workspace / "logs" / "health_check.log").read_text(encoding="utf-8")

    assert result["status"] == "OK"
    assert result["vz_cm_h"] == 13.5
    assert not curl_log.exists()
    assert "alerta de cheia não disparado" in log
