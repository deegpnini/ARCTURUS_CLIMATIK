#!/bin/bash
# ARCTURUS CLIMATIK - Motor de Execução Única (Disparado pelo Cron a cada 30 min)

BASE_DIR="/home/oikos/projetos/ARCTURUS_CLIMATIK"
cd $BASE_DIR

echo "============================================================" >> $BASE_DIR/logs/motor.log
echo "⏳ [$(date +'%Y-%m-%d %H:%M:%S')] Disparo do Ciclo Hidrológico" >> $BASE_DIR/logs/motor.log

# Ativa o ambiente virtual
source $BASE_DIR/.venv/bin/activate

# 1. Coleta da cota
python3 src/relatorios/coletar_tubarao_saneamento.py >> $BASE_DIR/logs/motor.log 2>&1


# 2. Confronto de chuva (Ensemble)
python3 src/relatorios/comparar_fontes_chuva.py >> $BASE_DIR/logs/motor.log 2>&1

# 3. Simulação de probabilidade (Classificador)
python3 src/modelo/simular_ensemble.py >> $BASE_DIR/logs/motor.log 2>&1

# 4. Cálculo da derivada (Vz)
python3 src/relatorios/monitor_derivada.py >> $BASE_DIR/logs/motor.log 2>&1

echo "✅ [$(date +'%Y-%m-%d %H:%M:%S')] Ciclo finalizado." >> $BASE_DIR/logs/motor.log
