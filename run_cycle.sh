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

trap 'flock -u 9' EXIT

cd "$BASE_DIR"

# Atualiza previsao meteorologica das 19 cidades se tiver mais de 3h (10800s)
if [ ! -f "$BASE_DIR/data/previsao_tempo.json" ] || [ $(( $(date +%s) - $(stat -c %Y "$BASE_DIR/data/previsao_tempo.json") )) -gt 10800 ]; then
    "$PYTHON" "$BASE_DIR/src/coleta/baixar_previsao_tempo.py" >> "$BASE_DIR/logs/previsao_tempo.log" 2>&1 || true
fi


# 1. Coleta primária em tempo real da Defesa Civil SC (ARIA DOM — 6 pontos da bacia)
"$PYTHON" "$BASE_DIR/src/coleta/coletar_defesacivil_sc.py" >> "$BASE_DIR/logs/defesacivil_sc.log" 2>&1 || true

# 2. Coleta complementar, fusão conservadora no PostgreSQL e modelos (v8 produção + backfill)
bash "$BASE_DIR/cron_motor.sh" &&
    "$PYTHON" "$BASE_DIR/src/relatorios/gravar_postgres.py" &&
    "$PYTHON" "$BASE_DIR/model_runner.py" &&
    "$PYTHON" "$BASE_DIR/backfill_y_true.py"

# 3. Modo Sombra v11c (LightGBM + Chuva Tripla — isolado de produção)
"$PYTHON" "$BASE_DIR/src/modelo/rodar_sombra_v11c.py" >> "$BASE_DIR/logs/sombra_v11c.log" 2>&1 || true

# 3.5 Validação contextual com comunicados oficiais (Defesa Civil SC / imprensa regional)
"$PYTHON" "$BASE_DIR/validar_contexto_noticias.py" >> "$BASE_DIR/logs/contexto_noticias.log" 2>&1 || true

# 4. Avaliação de cadência e envio do boletim (somente após coleta + banco + modelos concluídos)
if bash "$BASE_DIR/boletim_cadencia.sh" >> "$BASE_DIR/logs/boletim.log" 2>&1; then
    "$PYTHON" "$BASE_DIR/boletim_telegram.py" >> "$BASE_DIR/logs/boletim.log" 2>&1 || true
fi

# Rastreamento automatico de lag hidrologico (chuva -> ERAB)
.venv/bin/python3 src/analise/atualizar_lag_eventos.py >> logs/lag_eventos.log 2>&1 || true
