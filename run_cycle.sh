#!/usr/bin/env bash

log_timeout() {
    local rc=$1
    local passo=$2
    if [ "$rc" -eq 124 ] || [ "$rc" -eq 137 ]; then
        echo "[$(date '+%F %T')] TIMEOUT rc=$rc passo=$passo" >> "$BASE_DIR/logs/ciclo_completo.log"
    fi
}
set -euo pipefail

BASE_DIR="/home/oikos/projetos/ARCTURUS_CLIMATIK"
PYTHON="$BASE_DIR/.venv/bin/python3"
LOCK_FILE="/tmp/arcturus.lock"

exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Ciclo ignorado: outro ciclo está em execução."
    { date '+[%Y-%m-%d %H:%M:%S]'; ps -ef 2>/dev/null || ps; } 9>&- >> "$BASE_DIR/logs/lock_diag.log" 2>&1 || true
    exit 0
fi

trap 'flock -u 9' EXIT

cd "$BASE_DIR"

# Atualiza previsao meteorologica das 19 cidades se tiver mais de 3h (10800s)
if [ ! -f "$BASE_DIR/data/previsao_tempo.json" ] || [ $(( $(date +%s) - $(stat -c %Y "$BASE_DIR/data/previsao_tempo.json") )) -gt 10800 ]; then
    timeout -k 30 240 "$PYTHON" "$BASE_DIR/src/coleta/baixar_previsao_tempo.py" 9>&- >> "$BASE_DIR/logs/previsao_tempo.log" 2>&1
    log_timeout $? baixar_previsao_tempo
fi


# 1. Coleta primária em tempo real da Defesa Civil SC (ARIA DOM — 6 pontos da bacia)
timeout -k 30 240 "$PYTHON" "$BASE_DIR/src/coleta/coletar_defesacivil_sc.py" 9>&- >> "$BASE_DIR/logs/defesacivil_sc.log" 2>&1
log_timeout $? coletar_defesacivil_sc

# 2. Coleta complementar, fusão conservadora no PostgreSQL e modelos (v8 produção + backfill)
timeout -k 30 240 bash "$BASE_DIR/cron_motor.sh" 9>&-
log_timeout $? cron_motor
timeout -k 30 240 "$PYTHON" "$BASE_DIR/src/relatorios/gravar_postgres.py" 9>&-
log_timeout $? gravar_postgres
timeout -k 30 240 "$PYTHON" "$BASE_DIR/model_runner.py" 9>&-
log_timeout $? model_runner
timeout -k 30 240 "$PYTHON" "$BASE_DIR/backfill_y_true.py" 9>&-
log_timeout $? backfill_y_true

# 3. Modo Sombra v11c (LightGBM + Chuva Tripla — isolado de produção)
timeout -k 30 240 "$PYTHON" "$BASE_DIR/src/modelo/rodar_sombra_v11c.py" 9>&- >> "$BASE_DIR/logs/sombra_v11c.log" 2>&1
log_timeout $? rodar_sombra_v11c

# 3.2 Contorno de jusante: maré e vento costeiro em Laguna (remanso lagunar)
timeout -k 30 240 "$PYTHON" "$BASE_DIR/src/coleta/coletar_mare_laguna.py" 9>&- >> "$BASE_DIR/logs/mare_laguna.log" 2>&1
log_timeout $? coletar_mare_laguna

# 3.3 Coleta prospectiva pareada (forecast_runs + forecast_predictions: persistencia vs v8 vs fisica_3bracos v1.0)
timeout -k 30 240 "$PYTHON" "$BASE_DIR/src/modelo/executar_rodada_prospectiva.py" 9>&- >> "$BASE_DIR/logs/prospectivo.log" 2>&1
log_timeout $? executar_rodada_prospectiva

# 3.4 Comparacao condicional em modo sombra (nao envia Telegram nem altera o boletim oficial)
if timeout -k 30 240 "$PYTHON" "$BASE_DIR/boletim_sombra.py" 9>&- >> "$BASE_DIR/logs/boletim_sombra.log" 2>&1; then
    :
else
    rc=$?
    log_timeout "$rc" boletim_sombra
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] AVISO: boletim_sombra terminou com rc=$rc; modo oficial nao foi alterado" >> "$BASE_DIR/logs/ciclo_completo.log"
fi

# 3.5 Validação contextual com comunicados oficiais (Defesa Civil SC / imprensa regional)
timeout -k 30 240 "$PYTHON" "$BASE_DIR/validar_contexto_noticias.py" 9>&- >> "$BASE_DIR/logs/contexto_noticias.log" 2>&1
log_timeout $? validar_contexto_noticias

# 4. Avaliação de cadência e envio do boletim (somente após coleta + banco + modelos concluídos)
if bash "$BASE_DIR/boletim_cadencia.sh" >> "$BASE_DIR/logs/boletim.log" 2>&1; then
    timeout -k 30 240 "$PYTHON" "$BASE_DIR/boletim_telegram.py" 9>&- >> "$BASE_DIR/logs/boletim.log" 2>&1
    log_timeout $? boletim_telegram
fi

# Rastreamento automatico de lag hidrologico (chuva -> ERAB)
timeout -k 30 240 .venv/bin/python3 src/analise/atualizar_lag_eventos.py 9>&- >> logs/lag_eventos.log 2>&1
log_timeout $? atualizar_lag_eventos
