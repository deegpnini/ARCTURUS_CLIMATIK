#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT/.env"
LOG_FILE="$ROOT/logs/health_check.log"
LIMIT_MIN="${HEALTH_CHECK_LIMIT_MIN:-45}"

mkdir -p "$ROOT/logs"

log() {
    printf '%s %s\n' "$(date --iso-8601=seconds)" "$1" | tee -a "$LOG_FILE"
}

if [[ ! "$LIMIT_MIN" =~ ^[1-9][0-9]*$ ]]; then
    log "ERRO: HEALTH_CHECK_LIMIT_MIN deve ser um inteiro positivo."
    exit 2
fi

if [[ ! -r "$ENV_FILE" ]]; then
    log "ERRO: arquivo .env ausente ou ilegível: $ENV_FILE"
    exit 1
fi

set -a
source "$ENV_FILE"
set +a

IDADE="$(psql -XAtq -v ON_ERROR_STOP=1 -U oikos -d arcturus \
    -c "SELECT floor(extract(epoch FROM (localtimestamp - max(timestamp)))/60)::bigint FROM leituras;" 2>/dev/null)"

if [[ ! "$IDADE" =~ ^[0-9]+$ ]]; then
    log "ERRO: idade da última leitura indisponível ou inválida."
    exit 1
fi

if (( IDADE >= LIMIT_MIN )); then
    MSG="⚠️ ALERTA ARCTURUS: última leitura há $IDADE min (limite: $LIMIT_MIN min). O cron pode estar parado."

    if [[ -z "${TELEGRAM_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
        log "ERRO: leitura atrasada ($IDADE min), mas TELEGRAM_TOKEN/TELEGRAM_CHAT_ID não estão configurados no .env."
        exit 1
    fi

    RESPONSE="$(curl --silent --show-error --fail \
        --connect-timeout 10 --max-time 30 \
        --request POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${MSG}")" || {
        log "ERRO: falha HTTP ao enviar o alerta ao Telegram (leitura há $IDADE min)."
        exit 1
    }

    if ! python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("ok") is True else 1)' <<< "$RESPONSE"; then
        log "ERRO: Telegram API não confirmou o envio (leitura há $IDADE min)."
        exit 1
    fi

    log "ALERTA ENVIADO: leitura há $IDADE min (limite: $LIMIT_MIN min); Telegram confirmou o envio."
else
    log "OK: última leitura há $IDADE min (limite: $LIMIT_MIN min)."
fi
