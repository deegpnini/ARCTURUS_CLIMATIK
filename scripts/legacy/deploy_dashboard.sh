#!/bin/bash
DASHBOARD_DIR=~/ARCTURUS_DASHBOARD
CACHE_DIR=~/ARCTURUS_CLIMATIK/cache
LOG_FILE=~/ARCTURUS_CLIMATIK/logs/deploy.log

mkdir -p ~/ARCTURUS_CLIMATIK/logs
echo "[$(date '+%d/%m/%Y %H:%M')] Iniciando deploy..." >> "$LOG_FILE"

for arquivo in arcturus_alerta.json arcturus_hidro.json arcturus_sismico.json arcturus_sar.json; do
    if [ -f "$CACHE_DIR/$arquivo" ]; then
        cp "$CACHE_DIR/$arquivo" "$DASHBOARD_DIR/"
        echo "  OK $arquivo copiado" >> "$LOG_FILE"
    else
        echo "  AVISO $arquivo nao encontrado" >> "$LOG_FILE"
    fi
done

cd "$DASHBOARD_DIR" || exit 1

if git diff --quiet && git diff --cached --quiet; then
    echo "[$(date '+%d/%m/%Y %H:%M')] Sem mudancas." >> "$LOG_FILE"
    exit 0
fi

git add *.json *.html 2>/dev/null
git commit -m "update: $(date '+%Y-%m-%d %H:%M')" >> "$LOG_FILE" 2>&1
git push origin main >> "$LOG_FILE" 2>&1

echo "[$(date '+%d/%m/%Y %H:%M')] Deploy concluido." >> "$LOG_FILE"
echo "---" >> "$LOG_FILE"
