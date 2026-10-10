import csv
from pathlib import Path

# Ver o arquivo recuperados
path = Path("data/_backup/cache/cotas_84580000_RECUPERADOS_CONSOLIDADO.csv")
if path.exists():
    with path.open(encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    print(f"Total: {len(rows)}")
    print(f"Colunas: {list(rows[0].keys())}")
    print()
    print("Ultimas 20 linhas:")
    for r in rows[-20:]:
        print(f"  {r}")
else:
    print("Arquivo nao encontrado")

# Ver se o 446 aparece em outros arquivos
print()
print("=== Procurando '446' em data/ ===")
for p in sorted(Path("data").rglob("*.csv")):
    try:
        with p.open(encoding="utf-8-sig") as f:
            txt = f.read()
        if "446" in txt:
            count = txt.count("446")
            print(f"  {p}: {count} ocorrencias de '446'")
    except:
        pass
