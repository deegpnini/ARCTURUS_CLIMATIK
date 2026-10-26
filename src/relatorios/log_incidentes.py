import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
LOG_PATH = BASE / "data" / "log_incidentes.jsonl"

def registrar(evento, detalhes):
    entrada = {
        "timestamp": datetime.now().isoformat(),
        "evento": evento,
        "detalhes": detalhes
    }
    with open(LOG_PATH, "a") as f:
        f.write(json.dumps(entrada, ensure_ascii=False) + "\n")
    print(f"📝 Incidente registrado: {evento}")
