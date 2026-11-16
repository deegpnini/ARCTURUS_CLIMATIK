#!/usr/bin/env bash
set -euo pipefail

echo "=================================================="
echo "ARCTURUS - DIAGNOSTICO COMPLETO"
echo "=================================================="
echo
echo "=== 1. EVENTO ATUAL DA BACIA ==="
if [ -f data/evento_atual_bacia.json ]; then
    cat data/evento_atual_bacia.json
else
    echo "[AVISO] data/evento_atual_bacia.json ainda nao encontrado."
fi
echo
echo
echo "=== 2. HISTORICO DE SNAPSHOTS ==="
if [ -f data/eventos_hidrologicos.jsonl ]; then
    echo "Total de registros: $(wc -l < data/eventos_hidrologicos.jsonl)"
    echo "--- Ultimos 3 snapshots ---"
    tail -n 3 data/eventos_hidrologicos.jsonl
else
    echo "[AVISO] data/eventos_hidrologicos.jsonl ainda nao encontrado."
fi
echo
echo "=== 3. ULTIMA LEITURA DO RIO (ERAB - PostgreSQL) ==="
psql -d arcturus -c "
SELECT
    timestamp,
    cota_cm,
    vz_cm_h,
    az_cm_h2,
    regime,
    chuva_pior_caso_mm,
    qc
FROM leituras
ORDER BY timestamp DESC
LIMIT 5;
"
echo
echo "=== 4. RASTREAMENTO DE LAG (lag_eventos.jsonl) ==="
if [ -f data/lag_eventos.jsonl ]; then
    tail -n 3 data/lag_eventos.jsonl
else
    echo "[INFO] data/lag_eventos.jsonl sera criado no Passo 2."
fi
echo
echo "=== FIM ==="
