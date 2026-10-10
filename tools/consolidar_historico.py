"""
Consolida historico (CSV) + mes faltante (JSON).
Gera um arquivo unico por estacao, deduplicado por Data_Hora_Medicao.
"""
import csv, json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parent.parent
HIST = ROOT / "data" / "historico_montante"
FALT = ROOT / "data" / "historico_montante_faltante"
OUT = ROOT / "data" / "consolidado"
OUT.mkdir(exist_ok=True)

ESTACOES = {
    "84249998": "ORLEANS_MONTANTE",
    "84538500": "SAO_MAURICIO_JUSANTE",
    "84536000": "RIO_FORTUNA_JUSANTE",
}

for code, nome in ESTACOES.items():
    print(f"\n{'='*70}")
    print(f"Consolidando {nome} ({code})")
    print(f"{'='*70}")

    registros = {}

    # 1. Ler CSV
    csv_file = next(HIST.glob(f"{code}_*.csv"), None)
    if csv_file:
        with csv_file.open(encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            for row in reader:
                ts = row.get("Data_Hora_Medicao")
                if ts:
                    registros[ts] = row
        print(f"  CSV: {csv_file.name} -> {len(registros)} registros")

    # 2. Ler JSON
    json_file = next(FALT.glob(f"{code}_*.json"), None)
    if json_file:
        items = json.loads(json_file.read_text(encoding="utf-8"))
        novos = 0
        for item in items:
            ts = item.get("Data_Hora_Medicao")
            if ts and ts not in registros:
                registros[ts] = item
                novos += 1
        print(f"  JSON: {json_file.name} -> {novos} novos (de {len(items)})")

    # 3. Ordenar
    rows = sorted(registros.values(), key=lambda r: r.get("Data_Hora_Medicao", ""))
    print(f"  Total consolidado: {len(rows)}")

    if rows:
        print(f"  Primeira: {rows[0].get('Data_Hora_Medicao')}")
        print(f"  Ultima:   {rows[-1].get('Data_Hora_Medicao')}")

    # 4. Salvar
    out_file = OUT / f"{code}_{nome}_consolidado.csv"
    fields = sorted({k for row in rows for k in row.keys()})
    with out_file.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  [OK] {out_file.name} ({out_file.stat().st_size/1024:.0f} KB)")
