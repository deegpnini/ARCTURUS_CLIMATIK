#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
ENV_FILE="$ROOT/.env"
LOG_FILE="$ROOT/logs/health_check.log"
JSON_FILE="$ROOT/data/health_check.json"
LIMIT_MIN="${HEALTH_CHECK_LIMIT_MIN:-45}"

mkdir -p "$ROOT/logs" "$ROOT/data"

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

VZ_DATA="$(psql -XAtq -F '|' -v ON_ERROR_STOP=1 -U oikos -d arcturus \
    -c "WITH rolling AS (
            SELECT timestamp, id,
                   AVG(vz_cm_h) OVER (
                       ORDER BY timestamp, id
                       ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                   ) AS vz_suavizado,
                   COUNT(vz_cm_h) OVER (
                       ORDER BY timestamp, id
                       ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
                   ) AS leituras_validas
            FROM leituras
        ),
        ultimas AS (
            SELECT vz_suavizado, leituras_validas
            FROM rolling
            ORDER BY timestamp DESC, id DESC
            LIMIT 2
        )
        SELECT COALESCE(
                   (SELECT ROUND(vz_suavizado::numeric, 2)::text
                    FROM rolling
                    ORDER BY timestamp DESC, id DESC
                    LIMIT 1),
                   '0'
               ),
               CASE
                   WHEN COUNT(*) = 2
                    AND BOOL_AND(leituras_validas = 3 AND vz_suavizado > 12)
                   THEN 'true'
                   ELSE 'false'
               END
        FROM ultimas;" 2>/dev/null)"
IFS='|' read -r VZ_SUAVIZADO ALERTA_CHEIA <<< "$VZ_DATA"
if [[ ! "${VZ_SUAVIZADO:-}" =~ ^-?[0-9]+([.][0-9]+)?$ ]] \
    || [[ "${ALERTA_CHEIA:-}" != "true" && "${ALERTA_CHEIA:-}" != "false" ]]; then
    log "ERRO: Vz suavizado ou confirmação de cheia indisponível/inválida."
    exit 1
fi

REGIME="$(psql -XAtq -v ON_ERROR_STOP=1 -U oikos -d arcturus \
    -c "SELECT COALESCE(regime, 'NORMAL') FROM leituras ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null)"

STATUS="OK"
MSG=""
if (( IDADE >= LIMIT_MIN )); then
    STATUS="ALERTA"
    MSG="⚠️ ALERTA ARCTURUS: última leitura há $IDADE min (limite: $LIMIT_MIN min). O cron pode estar parado."
    MOTIVO="alerta disparado por leitura atrasada ($IDADE min; limite: $LIMIT_MIN min)"
elif [[ "$ALERTA_CHEIA" == "true" ]]; then
    STATUS="ALERTA"
    MSG="⚠️ ALERTA DE CHEIA: Vz suavizado = $VZ_SUAVIZADO cm/h em 2 leituras consecutivas. O rio está subindo rápido."
    MOTIVO="alerta de cheia disparado: Vz suavizado acima de 12 cm/h em 2 leituras consecutivas"
else
    MOTIVO="alerta de cheia não disparado: são necessárias 2 médias móveis consecutivas acima de 12 cm/h"
fi
log "Vz suavizado (média móvel de 3 leituras): $VZ_SUAVIZADO cm/h."
log "Decisão: $MOTIVO."

if [[ "$STATUS" == "ALERTA" ]]; then
    if [[ -z "${TELEGRAM_TOKEN:-}" || -z "${TELEGRAM_CHAT_ID:-}" ]]; then
        log "ERRO: alerta necessário, mas TELEGRAM_TOKEN/TELEGRAM_CHAT_ID não estão configurados no .env."
        exit 1
    fi

    RESPONSE="$(curl --silent --show-error --fail \
        --connect-timeout 10 --max-time 30 \
        --request POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${MSG}")" || {
        log "ERRO: falha HTTP ao enviar o alerta ao Telegram ($MOTIVO)."
        exit 1
    }

    if ! python3 -c 'import json,sys; sys.exit(0 if json.load(sys.stdin).get("ok") is True else 1)' <<< "$RESPONSE"; then
        log "ERRO: Telegram API não confirmou o envio ($MOTIVO)."
        exit 1
    fi
    log "ALERTA ENVIADO: $MOTIVO; Telegram confirmou o envio."
else
    log "OK: última leitura há $IDADE min (limite: $LIMIT_MIN min)."
fi

cat > "$JSON_FILE" << JSONEOF
{
  "timestamp": "$(date -Iseconds)",
  "status": "$STATUS",
  "idade_min": $IDADE,
  "limite_min": $LIMIT_MIN,
  "vz_cm_h": $VZ_SUAVIZADO,
  "regime": "$REGIME",
  "mensagem": "$MSG"
}
JSONEOF
log "JSON atualizado: $JSON_FILE"
