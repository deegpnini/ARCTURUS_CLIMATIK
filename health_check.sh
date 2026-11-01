#!/bin/bash
set -euo pipefail

# Carrega credenciais (ignora se nao existir)
if [ -f "$(dirname "$0")/.env" ]; then
    set -a; source "$(dirname "$0")/.env" 2>/dev/null || true; set +a
fi

# --- INICIO DA CHECAGEM DE FRESCOR ---
# So executa se NAO estivermos em modo de teste
if [ "${SKIP_STALE_CHECK:-0}" != "1" ]; then
    LIMITE_MIN=45
    STATE_FILE="$(dirname "$0")/.last_stale_alert"
    JSON_COTA="$(dirname "$0")/tubarao_saneamento_dados.json"

    # O '|| true' no final evita que o set -e mate o script se o JSON nao existir
    ULTIMA_LEITURA=$(python3 -c "import json; print(json.load(open('$JSON_COTA')).get('data_extracao', ''))" 2>/dev/null || true)
    
    if [ -n "$ULTIMA_LEITURA" ]; then
        AGORA=$(date +%s)
        TS_LEITURA=$(date -d "$ULTIMA_LEITURA" +%s 2>/dev/null || true)
        
        if [ -n "$TS_LEITURA" ]; then
            DIF_MIN=$(( (AGORA - TS_LEITURA) / 60 ))
            if [ "$DIF_MIN" -gt "$LIMITE_MIN" ]; then
                if [ -f "$STATE_FILE" ] && [ $(( (AGORA - $(cat "$STATE_FILE")) / 60 )) -lt 240 ]; then
                    echo "{"status": "STALE", "minutos": $DIF_MIN, "alerta_silenciado": true}" > "$(dirname "$0")/data/health_check.json"
                    exit 0
                fi
                echo "$AGORA" > "$STATE_FILE"
                MSG="⚠️ ALERTA ARCTURUS: ultima leitura ha $DIF_MIN min (limite: $LIMITE_MIN min)."
                if [ -n "${TELEGRAM_TOKEN:-}" ] && [ -n "${TELEGRAM_CHAT_ID:-}" ]; then
                    curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" --data-urlencode "chat_id=${TELEGRAM_CHAT_ID}" --data-urlencode "text=$MSG" > /dev/null || true
                fi
                echo "{"status": "STALE", "minutos": $DIF_MIN}" > "$(dirname "$0")/data/health_check.json"
                exit 0
            else
                rm -f "$STATE_FILE"
                echo "{"status": "OK", "minutos": $DIF_MIN}" > "$(dirname "$0")/data/health_check.json"
            fi
        fi
    fi
fi
# --- FIM DA CHECAGEM DE FRESCOR ---


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

# 2. Suaviza o Vz, exige cota ascendente e confirma em duas leituras.
VZ_DATA="$(psql -XAtq -F '|' -v ON_ERROR_STOP=1 -U oikos -d arcturus \
    -c "WITH rolling AS (
            SELECT timestamp, id, cota_cm,
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
        ordenadas AS (
            SELECT *, LAG(cota_cm) OVER (ORDER BY timestamp, id) AS cota_anterior
            FROM rolling
        )
        SELECT COALESCE(ROUND((SELECT vz_suavizado FROM ordenadas
                               ORDER BY timestamp DESC, id DESC LIMIT 1)::numeric, 2)::text, '0'),
               COALESCE((SELECT (cota_cm > cota_anterior)::text
                         FROM ordenadas ORDER BY timestamp DESC, id DESC LIMIT 1), 'false'),
               COALESCE((SELECT BOOL_AND(leituras_validas = 3
                                         AND vz_suavizado > 12
                                         AND cota_cm > cota_anterior)::text
                         FROM (SELECT * FROM ordenadas
                               ORDER BY timestamp DESC, id DESC LIMIT 2) recentes
                         HAVING COUNT(*) = 2), 'false'),
               COALESCE((SELECT BOOL_AND(leituras_validas = 3
                                         AND vz_suavizado > 52
                                         AND cota_cm > cota_anterior)::text
                         FROM (SELECT * FROM ordenadas
                               ORDER BY timestamp DESC, id DESC LIMIT 2) recentes
                         HAVING COUNT(*) = 2), 'false'),
               COALESCE((SELECT BOOL_AND(leituras_validas = 3
                                         AND vz_suavizado > 12
                                         AND cota_cm > cota_anterior)::text
                         FROM (SELECT * FROM ordenadas
                               ORDER BY timestamp DESC, id DESC LIMIT 4) recentes
                         HAVING COUNT(*) = 4), 'false')
        ;" 2>/dev/null)"
IFS='|' read -r VZ_SUAVIZADO COTA_SUBINDO ALERTA_CHEIA ALERTA_EXTREMO ALERTA_PERSISTENTE <<< "$VZ_DATA"
if [[ ! "${VZ_SUAVIZADO:-}" =~ ^-?[0-9]+([.][0-9]+)?$ ]] \
    || [[ "${COTA_SUBINDO:-}" != "true" && "${COTA_SUBINDO:-}" != "false" ]] \
    || [[ "${ALERTA_CHEIA:-}" != "true" && "${ALERTA_CHEIA:-}" != "false" ]] \
    || [[ "${ALERTA_EXTREMO:-}" != "true" && "${ALERTA_EXTREMO:-}" != "false" ]] \
    || [[ "${ALERTA_PERSISTENTE:-}" != "true" && "${ALERTA_PERSISTENTE:-}" != "false" ]]; then
    log "ERRO: Vz suavizado ou confirmação de cheia indisponível/inválida."
    exit 1
fi

# Chuva a montante é um dado auxiliar; indisponibilidade não confirma chuva.
CHUVA_DATA="$(python3 - "$BASE_DIR/data/chuva_montante.csv" <<'PY'
import csv
import datetime
import sys

try:
    with open(sys.argv[1], newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    rows = sorted(
        (row for row in rows if row.get("data") and row.get("chuva_montante_24h")),
        key=lambda row: row["data"],
    )
    if not rows:
        raise ValueError("no rainfall rows")
    latest = rows[-1]
    age = (datetime.date.today() - datetime.date.fromisoformat(latest["data"])).days
    if age < 0 or age > 1:
        raise ValueError("rainfall data is stale")
    print(latest["chuva_montante_24h"])
except (OSError, ValueError, KeyError):
    print("N/A")
PY
)"
if [[ "$CHUVA_DATA" =~ ^-?[0-9]+([.][0-9]+)?$ ]]; then
    CHUVA_MONTANTE_24H="$CHUVA_DATA"
else
    CHUVA_MONTANTE_24H="N/A"
fi

# 3. Verifica o regime
REGIME="$(psql -XAtq -v ON_ERROR_STOP=1 -U oikos -d arcturus \
    -c "SELECT COALESCE(regime, 'NORMAL') FROM leituras ORDER BY timestamp DESC LIMIT 1;" 2>/dev/null)"

# 4. Define o status (OK ou ALERTA)
STATUS="OK"
MSG=""
MOTIVO=""
NIVEL_ALERTA="NORMAL"
if (( IDADE >= LIMIT_MIN )); then
    STATUS="ALERTA"
    MSG="⚠️ ALERTA ARCTURUS: última leitura há $IDADE min (limite: $LIMIT_MIN min). O cron pode estar parado."
    MOTIVO="alerta disparado por leitura atrasada ($IDADE min; limite: $LIMIT_MIN min)"
elif [[ "$ALERTA_CHEIA" == "true" ]]; then
    STATUS="ALERTA"
    NIVEL_ALERTA="ATENCAO"
    if [[ "$ALERTA_EXTREMO" == "true" ]]; then
        NIVEL_ALERTA="EXTREMO"
    fi
    MSG="⚠️ ALERTA DE CHEIA ($NIVEL_ALERTA): Vz suavizado = $VZ_SUAVIZADO cm/h em 2 leituras consecutivas; cota subindo."
    REGIME="$NIVEL_ALERTA"
    MOTIVO="alerta de cheia disparado ($NIVEL_ALERTA): Vz suavizado acima do limiar em 2 leituras consecutivas e cota subindo"
    if [[ "$ALERTA_PERSISTENTE" == "true" ]]; then
        MOTIVO="$MOTIVO; persistente por mais de 3 leituras consecutivas"
    fi
    if [[ "$CHUVA_MONTANTE_24H" =~ ^[0-9]+([.][0-9]+)?$ ]] \
        && awk -v chuva="$CHUVA_MONTANTE_24H" 'BEGIN { exit !(chuva > 50) }'; then
        MSG="$MSG ALERTA REFORÇADO: Vz alto + chuva a montante (${CHUVA_MONTANTE_24H} mm/24h)."
        MOTIVO="$MOTIVO; alerta reforçado por chuva a montante acima de 50 mm/24h"
    fi
else
    MOTIVO="alerta de cheia não disparado: requer Vz suavizado acima de 12 cm/h em 2 leituras consecutivas e cota subindo"
fi
log "Vz suavizado (média móvel de 3 leituras): $VZ_SUAVIZADO cm/h."
log "Cota subindo: $COTA_SUBINDO; alerta extremo confirmado: $ALERTA_EXTREMO; persistente (>3 leituras): $ALERTA_PERSISTENTE."
log "Chuva a montante 24h: $CHUVA_MONTANTE_24H mm."
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
  "cota_subindo": $COTA_SUBINDO,
  "nivel_alerta": "$NIVEL_ALERTA",
  "alerta_persistente": $ALERTA_PERSISTENTE,
  "chuva_montante_24h_mm": "$CHUVA_MONTANTE_24H",
  "regime": "$REGIME",
  "mensagem": "$MSG"
}
JSONEOF

log "JSON atualizado: $JSON_FILE"
