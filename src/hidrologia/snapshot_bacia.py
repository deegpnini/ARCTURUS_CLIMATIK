#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime

BASE = Path("/home/oikos/projetos/ARCTURUS_CLIMATIK")

DC = BASE / "data" / "chuva_defesacivil_realtime.json"
OUT = BASE / "data" / "eventos_hidrologicos.jsonl"

dados = json.loads(DC.read_text())

maximo = 0
dominante = "DESCONHECIDA"

for e in dados["estacoes"]:
    c24 = e.get("chuva_24h_mm")

    if c24 is None:
        continue

    if float(c24) > maximo:
        maximo = float(c24)
        dominante = e["trecho_bacia"]

registro = {
    "timestamp": datetime.now().isoformat(),
    "estacao_dominante": dominante,
    "chuva_max_24h": maximo,
    "chuva_max_6h": dados["pior_caso_bacia"]["max_chuva_6h_mm"],
}

with open(OUT, "a", encoding="utf-8") as f:
    f.write(json.dumps(registro, ensure_ascii=False))
    f.write("\n")

print("✅ Snapshot salvo")
