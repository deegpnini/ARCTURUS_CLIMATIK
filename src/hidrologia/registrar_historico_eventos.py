#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime

BASE = Path("/home/oikos/projetos/ARCTURUS_CLIMATIK")

ARQ = BASE / "data" / "chuva_defesacivil_realtime.json"

OUT = BASE / "data" / "eventos_hidrologicos.jsonl"

dados = json.loads(ARQ.read_text())

registro = {
    "timestamp": datetime.now().isoformat(),
    "max_24h": dados["pior_caso_bacia"]["max_chuva_24h_mm"],
    "max_6h": dados["pior_caso_bacia"]["max_chuva_6h_mm"],
    "estacoes": dados["estacoes"]
}

with open(OUT, "a", encoding="utf-8") as f:
    f.write(json.dumps(registro, ensure_ascii=False))
    f.write("\n")

print("✅ Histórico atualizado.")
