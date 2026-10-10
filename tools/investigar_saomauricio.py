import json, csv
from pathlib import Path

# 1. Inventario
inv = json.load(open("data/ana_inventario_sc.json", encoding="utf-8"))
items = inv if isinstance(inv, list) else next(v for v in inv.values() if isinstance(v, list))

for code in ["84538500", "84536000", "84580000"]:
    est = next((i for i in items if str(i.get("codigoestacao")) == code), None)
    if est:
        print(f"--- {code} ({est.get('Estacao_Nome')}) ---")
        print(f"  Escala: {est.get('Tipo_Estacao_Escala')}")
        print(f"  Operadora: {est.get('Operadora_Sigla')}")
        print(f"  Area drenagem: {est.get('Area_Drenagem')} km²")
        print(f"  Telemetrica: {est.get('Tipo_Estacao_Telemetrica')}")
        print()

# 2. Distribuicao de Cota_Adotada_Status no CSV
print("=== Distribuicao de Cota_Adotada_Status ===")
for name in ["84538500_SAO_MAURICIO_JUSANTE", "84536000_RIO_FORTUNA_JUSANTE"]:
    path = Path(f"data/consolidado/{name}_consolidado.csv")
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    from collections import Counter
    status = Counter(r.get("Cota_Adotada_Status") for r in rows)
    print(f"\n{name}:")
    for s, n in status.most_common():
        print(f"  Status={s!r}: {n} registros")
