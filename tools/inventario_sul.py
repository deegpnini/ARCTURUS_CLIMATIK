import json
from collections import Counter
inv = json.load(open("data/ana_inventario_sc.json", encoding="utf-8"))
items = inv if isinstance(inv, list) else next(v for v in inv.values() if isinstance(v, list))
print(len(items), "estacoes"); print("CAMPOS:", list(items[0].keys())); print("EXEMPLO:", items[0])
ck = next(k for k in items[0] if "odigo" in k and "stac" in k)
print("Prefixos de codigo:", Counter(str(i[ck])[:2] for i in items).most_common(12))
sul = [i for i in items if str(i[ck]).startswith("84")]
print(len(sul), "estacoes com codigo 84* (mesmo prefixo de Tubarao e Ermo)")
for i in sul[:40]:
    print({k: v for k, v in i.items() if any(t in k.lower() for t in ("codigo", "nome", "rio", "tipo", "telem", "area"))})
