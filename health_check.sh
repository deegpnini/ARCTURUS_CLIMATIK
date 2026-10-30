#!/bin/bash
set -euo pipefail

BASE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="$BASE_DIR/logs/health_check.log"
ENV_FILE="$BASE_DIR/.env"
JSON_FILE="$BASE_DIR/data/health_check.json"

LIMIT_MIN="${LIMIT_MIN:-45}"

mkdir -p "$BASE_DIR/logs" "$BASE_DIR/data"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" >> "$LOG_FILE"
}

if [[ ! -r "$ENV_FILE" ]]; then
    log "ERRO: arquivo .env ausente ou ilegível: $ENV_FILE"
    exit 1
fi
set -a
source "$ENV_FILE"
set +a

# 1. Verifica a idade da última leitura
IDADE="$(psql -XAtq -v ON_ERROR_STOP=1 -U oikos -d arcturus \
    -c "SELECT floor(extract(epoch FROM (localtimestamp - max(timestamp)))/60)::bigint FROM leituras;" 2>/dev/null)"

if [[ ! "$IDADE" =~ ^[0-9]+$ ]]; then
    log "ERRO: idade da última leitura indisponível ou inválida."
    exit 1
fi

# 2. Suaviza o Vz com a média móvel de 3 leituras e exige 2 médias altas
# consecutivas para confirmar um alerta de cheia.
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

# 3. Verifica o regime
REGIME="$(psql -XAtq -v ON_ERROR_STOP=1 -U oikos -d arcturus \
    -c "SELECT COALESCE(regime, 'NORMAL') FROM leituras ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null)"

# 4. Define o status (OK ou ALERTA)
STATUS="OK"
MSG=""
MOTIVO=""
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

# 5. Se houver alerta, envia para o Telegram
if [[ "$STATUS" == "ALERTA" ]] && [[ -n "${TELEGRAM_TOKEN:-}" ]] && [[ -n "${TELEGRAM_CHAT_ID:-}" ]]; then
    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
        --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" \
        --data-urlencode "text=${MSG}" > /dev/null
fi

# 6. Escreve o JSON (para o Dash ler)
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
