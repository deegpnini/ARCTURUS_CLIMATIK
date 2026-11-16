#!/usr/bin/env python3

import json
from pathlib import Path
from datetime import datetime

BASE = Path("/home/oikos/projetos/ARCTURUS_CLIMATIK")

arquivo = BASE / "data" / "chuva_defesacivil_realtime.json"

saida = BASE / "data" / "evento_atual_bacia.json"

dados = json.loads(
    arquivo.read_text(encoding="utf-8")
)

estacoes = dados.get("estacoes", [])

chuva_max = -1
dominante = None

for est in estacoes:

    c24 = est.get("chuva_24h_mm")

    if c24 is None:
        continue

    if float(c24) > chuva_max:
        chuva_max = float(c24)
        dominante = est

evento = {
    "timestamp": datetime.now().isoformat(),
    "evento_id": datetime.now().strftime("%Y%m%d_%H%M"),
    "chuva_max_24h": chuva_max,
    "estacao_dominante": dominante["trecho_bacia"],
    "codigo_estacao": dominante["codigo"],
    "resumo": {}
}

for est in estacoes:

    evento["resumo"][est["trecho_bacia"]] = {
        "chuva_6h": est.get("chuva_6h_mm"),
        "chuva_24h": est.get("chuva_24h_mm"),
    }

saida.write_text(
    json.dumps(
        evento,
        indent=2,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

print("=" * 60)
print("EVENTO REGISTRADO")
print("=" * 60)
print("Estação dominante:", evento["estacao_dominante"])
print("Chuva 24h:", evento["chuva_max_24h"])
print("Arquivo:", saida)
