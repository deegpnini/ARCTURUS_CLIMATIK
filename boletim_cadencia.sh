#!/usr/bin/env bash
# ============================================================
# boletim_cadencia.sh — Decide se o boletim deve ser enviado
# ============================================================
set -euo pipefail

BASE_DIR="/home/oikos/projetos/ARCTURUS_CLIMATIK"
ESTADO_FILE="$BASE_DIR/data/boletim_estado.json"
LOG_FILE="$BASE_DIR/logs/boletim_cadencia.log"
PYTHON="$BASE_DIR/.venv/bin/python3"

mkdir -p "$BASE_DIR/data" "$BASE_DIR/logs"

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG_FILE"
}

# ------------------------------------------------------------
# 1. Lê cota, chuva_24h e vz do banco (última leitura válida)
# ------------------------------------------------------------
read -r COTA CHUVA VZ <<< "$(psql -d arcturus -tA -F' ' -c "
    SELECT
        COALESCE((SELECT cota_cm FROM leituras
                  WHERE cota_cm IS NOT NULL AND qc = 'VALIDO'
                  ORDER BY timestamp DESC LIMIT 1), 0),
        COALESCE((SELECT AVG(chuva_pior_caso_mm) FROM leituras
                  WHERE timestamp > NOW() - INTERVAL '24 hours'
                    AND chuva_pior_caso_mm IS NOT NULL), 0),
        COALESCE((SELECT ABS(vz_cm_h) FROM leituras
                  WHERE vz_cm_h IS NOT NULL AND qc = 'VALIDO'
                  ORDER BY timestamp DESC LIMIT 1), 0)
")"

log "Dados lidos: cota=${COTA}cm chuva_24h=${CHUVA}mm vz=${VZ}cm/h"

# ------------------------------------------------------------
# 2. Classifica o estado (limiares)
# ------------------------------------------------------------
python3 - "$COTA" "$CHUVA" "$VZ" "$ESTADO_FILE" "$LOG_FILE" << 'PY_EOF'
import json
import os
import sys
import time
from pathlib import Path

cota = float(sys.argv[1])
chuva = float(sys.argv[2])
vz = float(sys.argv[3])
estado_file = Path(sys.argv[4])
log_file = Path(sys.argv[5])

CADENCIAS = {"NORMAL": 60, "ATENCAO": 30, "ALERTA": 15, "EXTREMO": 5}
PESO = {"NORMAL": 1, "ATENCAO": 2, "ALERTA": 3, "EXTREMO": 4}

def classificar(c, ch, v):
    if c > 300 or ch > 50 or v > 10:
        return "EXTREMO"
    if c > 200 or ch > 20 or v > 5:
        return "ALERTA"
    if c > 100 or ch > 5 or v > 1:
        return "ATENCAO"
    return "NORMAL"

def ler_estado():
    if not estado_file.exists():
        return {"ultimo_envio": 0, "estado": "NORMAL"}
    try:
        with open(estado_file) as f:
            d = json.load(f)
    except (json.JSONDecodeError, OSError):
        return {"ultimo_envio": 0, "estado": "NORMAL"}
    if d.get("estado") not in PESO:
        d["estado"] = "NORMAL"
    return d

def gravar(ultimo_envio, estado):
    estado_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(estado_file) + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"ultimo_envio": ultimo_envio, "estado": estado}, f)
    os.replace(tmp, estado_file)

def log(msg):
    with open(log_file, "a") as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}\n")

agora = time.time()
estado_atual = classificar(cota, chuva, vz)
anterior = ler_estado()
ultimo = anterior["ultimo_envio"]
estado_velho = anterior["estado"]

piorou = PESO[estado_atual] > PESO[estado_velho]
cadencia_seg = CADENCIAS[estado_atual] * 60
decorrido = agora - ultimo

if piorou:
    log(f"PIOROU {estado_velho} -> {estado_atual}. ENVIAR.")
    gravar(agora, estado_atual)
    sys.exit(0)

if decorrido >= cadencia_seg:
    log(f"CADENCIA atingida ({CADENCIAS[estado_atual]}min, estado {estado_atual}). ENVIAR.")
    gravar(agora, estado_atual)
    sys.exit(0)

faltam = (cadencia_seg - decorrido) / 60
log(f"SUPRIMIR (estado {estado_atual}, proximo em {faltam:.0f}min).")
gravar(ultimo, estado_atual)
sys.exit(1)
PY_EOF

EXIT_CODE=$?
if [ $EXIT_CODE -eq 0 ]; then
    log ">>> DECISAO: ENVIAR boletim <<<"
    exit 0
else
    log ">>> DECISAO: SUPRIMIR boletim <<<"
    exit 1
fi
