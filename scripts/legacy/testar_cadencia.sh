#!/usr/bin/env bash
# ============================================================
# testar_cadencia.sh — Testa a logica com dados mockados
# ============================================================
set -u

BASE_DIR="/home/oikos/projetos/ARCTURUS_CLIMATIK"
ESTADO_FILE="$BASE_DIR/data/boletim_estado.json"
PYTHON="$BASE_DIR/.venv/bin/python3"

echo "============================================================"
echo " TESTE DA CADENCIA ADAPTATIVA"
echo "============================================================"

# Limpa o estado anterior
rm -f "$ESTADO_FILE"
echo "[setup] Estado limpo: $ESTADO_FILE"
echo ""

teste() {
    local cota=$1 chuva=$2 vz=$3 desc=$4
    echo "------------------------------------------------------------"
    echo "Cenario: $desc (cota=${cota}cm, chuva=${chuva}mm, vz=${vz}cm/h)"
    echo "------------------------------------------------------------"
    "$PYTHON" - "$cota" "$chuva" "$vz" "$ESTADO_FILE" << 'PY_EOF'
import json, os, sys, time
from pathlib import Path

cota, chuva, vz = float(sys.argv[1]), float(sys.argv[2]), float(sys.argv[3])
estado_file = Path(sys.argv[4])

CADENCIAS = {"NORMAL": 60, "ATENCAO": 30, "ALERTA": 15, "EXTREMO": 5}
PESO = {"NORMAL": 1, "ATENCAO": 2, "ALERTA": 3, "EXTREMO": 4}

def classificar(c, ch, v):
    if c > 300 or ch > 50 or v > 10: return "EXTREMO"
    if c > 200 or ch > 20 or v > 5:  return "ALERTA"
    if c > 100 or ch > 5 or v > 1:   return "ATENCAO"
    return "NORMAL"

def ler():
    if not estado_file.exists():
        return {"ultimo_envio": 0, "estado": "NORMAL"}
    try:
        with open(estado_file) as f:
            return json.load(f)
    except Exception:
        return {"ultimo_envio": 0, "estado": "NORMAL"}

def gravar(t, e):
    estado_file.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(estado_file) + ".tmp"
    with open(tmp, "w") as f:
        json.dump({"ultimo_envio": t, "estado": e}, f)
    os.replace(tmp, estado_file)

agora = time.time()
estado_atual = classificar(cota, chuva, vz)
ant = ler()
piorou = PESO[estado_atual] > PESO[ant["estado"]]
cad = CADENCIAS[estado_atual] * 60
decorrido = agora - ant["ultimo_envio"]

if piorou:
    print(f"  Estado: {ant['estado']} -> {estado_atual} (PIOROU)")
    print(f"  DECISAO: ENVIAR (alerta imediato)")
    gravar(agora, estado_atual)
    sys.exit(0)

if decorrido >= cad:
    print(f"  Estado: {estado_atual} (cadencia {CADENCIAS[estado_atual]}min atingida)")
    print(f"  DECISAO: ENVIAR")
    gravar(agora, estado_atual)
    sys.exit(0)

faltam = (cad - decorrido) / 60
print(f"  Estado: {estado_atual}")
print(f"  DECISAO: SUPRIMIR (proximo em {faltam:.0f}min)")
gravar(ant["ultimo_envio"], estado_atual)
sys.exit(1)
PY_EOF
    echo ""
}

# --- Cenario 1: NORMAL, primeira vez ---
teste 79 0 0 "NORMAL, primeira execucao (deve ENVIAR)"

# --- Cenario 2: NORMAL, logo depois (deve SUPRIMIR) ---
teste 79 0 0 "NORMAL, 1 min depois (deve SUPRIMIR)"

# --- Cenario 3: NORMAL, ainda suprimindo ---
teste 80 1 0 "NORMAL, 2 min depois (deve SUPRIMIR)"

# --- Cenario 4: PIORA para ALERTA (deve ENVIAR na hora) ---
teste 250 30 6 "PIOROU para ALERTA (deve ENVIAR imediato)"

# --- Cenario 5: ALERTA, logo depois (deve SUPRIMIR) ---
teste 250 30 6 "ALERTA, 1 min depois (deve SUPRIMIR)"

# --- Cenario 6: MELHORA para NORMAL (deve SUPRIMIR, cadencia 60min) ---
teste 79 0 0 "MELHOROU para NORMAL (deve SUPRIMIR, cadencia 60min)"

# --- Cenario 7: PIORA para EXTREMO (deve ENVIAR na hora) ---
teste 350 60 12 "PIOROU para EXTREMO (deve ENVIAR imediato)"

echo "============================================================"
echo " FIM DOS TESTES"
echo "============================================================"
echo ""
echo "Estado final:"
cat "$ESTADO_FILE" 2>/dev/null || echo "(sem estado)"
echo ""
