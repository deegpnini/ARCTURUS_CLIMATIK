#!/usr/bin/env bash
# Roda FORA do lock do ciclo. Uso: ./watchdog_arcturus.sh [limite_min]  (padrão 45)
cd /home/oikos/projetos/ARCTURUS_CLIMATIK || exit 1
set -a; . ./.env; set +a
limite=${1:-45}
idade=$(psql -d arcturus -Atc "SELECT COALESCE(EXTRACT(EPOCH FROM now()-max(ts_coleta))/60, 9999)::int FROM leituras" 2>/dev/null)
[ -z "$idade" ] && idade=9999
estado=/tmp/arcturus_watchdog.last
enviar() {
  curl -s -X POST "https://api.telegram.org/bot${TELEGRAM_TOKEN}/sendMessage" \
    -d chat_id="${TELEGRAM_CHAT_ID}" -d text="$1" >/dev/null
}
if [ "$idade" -gt "$limite" ]; then
  agora=$(date +%s); ultimo=$(cat "$estado" 2>/dev/null || echo 0)
  if [ $((agora - ultimo)) -ge 1800 ]; then
    nivel=ATENCAO; [ "$idade" -gt 120 ] && nivel=CRITICO
    enviar "ARCTURUS ${nivel}: sem dado novo da cota ha ${idade} min. Camada 1 pode estar cega; confira fonte oficial."
    echo "$agora" > "$estado"
  fi
else
  if [ -f "$estado" ]; then
    enviar "ARCTURUS: dado da cota normalizado (idade ${idade} min)."
    rm -f "$estado"
  fi
fi
