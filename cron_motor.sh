#!/bin/bash
# Camada 1 - Motor de Execução (roda a cada 15 min)

BASE_DIR="/home/oikos/projetos/ARCTURUS_CLIMATIK"
cd $BASE_DIR

echo "============================================================" >> $BASE_DIR/logs/motor.log
echo "⏳ [$(date +'%Y-%m-%d %H:%M:%S')] Disparo do Ciclo Hidrológico" >> $BASE_DIR/logs/motor.log

source $BASE_DIR/.venv/bin/activate

# 1. Coleta da cota (timeout de 2 min para não travar o resto)
timeout 120 python3 src/relatorios/coletar_tubarao_saneamento.py >> $BASE_DIR/logs/motor.log 2>&1
STATUS_SCRAPER=$?

# 2. Confronto de chuva
timeout 60 python3 src/relatorios/comparar_fontes_chuva.py >> $BASE_DIR/logs/motor.log 2>&1
STATUS_CHUVA=$?

# 3. Simulação de probabilidade
timeout 60 python3 src/modelo/simular_ensemble.py >> $BASE_DIR/logs/motor.log 2>&1
STATUS_ENSEMBLE=$?

# 4. Cálculo da derivada (Vz)
timeout 60 python3 src/relatorios/monitor_derivada.py >> $BASE_DIR/logs/motor.log 2>&1
STATUS_VZ=$?

if [ $STATUS_SCRAPER -ne 0 ] || [ $STATUS_CHUVA -ne 0 ] || [ $STATUS_ENSEMBLE -ne 0 ] || [ $STATUS_VZ -ne 0 ]; then
    echo "⚠️ [$(date +'%Y-%m-%d %H:%M:%S')] Ciclo concluído com falhas. Scraper:$STATUS_SCRAPER Chuva:$STATUS_CHUVA Ensemble:$STATUS_ENSEMBLE Vz:$STATUS_VZ" >> $BASE_DIR/logs/motor.log
else
    echo "✅ [$(date +'%Y-%m-%d %H:%M:%S')] Ciclo finalizado sem erros." >> $BASE_DIR/logs/motor.log
fi
