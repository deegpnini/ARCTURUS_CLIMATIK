#!/usr/bin/env bash
set -euo pipefail

BASE_DIR="/home/oikos/projetos/ARCTURUS_CLIMATIK"
PYTHON="$BASE_DIR/.venv/bin/python3"
LOCK_FILE="/tmp/arcturus.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ciclo ignorado: outro ciclo está em execução."
    exit 0
fi

# Trap: se o script sair (sucesso ou erro), destrava o lock explicitamente
trap 'flock -u 9' EXIT

cd "$BASE_DIR"

# Preserve the existing collection and hydrology processing pipeline.
bash "$BASE_DIR/cron_motor.sh" &&
    "$PYTHON" "$BASE_DIR/src/relatorios/gravar_postgres.py" &&
    "$PYTHON" "$BASE_DIR/model_runner.py" &&
    "$PYTHON" "$BASE_DIR/backfill_y_true.py"

# Modo Sombra v11c (LightGBM + Chuva Tripla)
.venv/bin/python3 src/modelo/rodar_sombra_v11c.py >> logs/sombra_v11c.log 2>&1 || true
