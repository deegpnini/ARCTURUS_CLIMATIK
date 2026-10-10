import json
from datetime import datetime
from pathlib import Path

def T(s):
    return datetime.fromisoformat(str(s).replace(" ", "T")[:19])

for p in sorted(Path(".").glob("data/**/telemetria_84580000_2026.json")):
    d = json.load(open(p, encoding="utf-8"))
    its = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
    print("\n###", p, "| n =", len(its))
    print("CAMPOS:", list(its[0].keys()))

    ck = next(k for k in its[0] if "cota" in k.lower())
    mk = "Data_Hora_Medicao" if "Data_Hora_Medicao" in its[0] else None

    if not mk:
        print("campo de medicao nao encontrado")
        continue

    rows = sorted((T(x[mk]), x) for x in its if x.get(mk))

    print("\nLeituras 21/09 19:00 a 22/09 03:00:")
    for dt, x in rows:
        if datetime(2026, 9, 21, 19) <= dt <= datetime(2026, 9, 22, 3):
            print(f"  {dt} | cota={x.get(ck)}")

    print("\nBuracos > 20 min entre 18/09 e 26/09:")
    prev = None
    for dt, _ in rows:
        if prev and (dt - prev).total_seconds() > 1200 and datetime(2026, 9, 18) <= dt <= datetime(2026, 9, 26):
            print(f"  {prev} -> {dt} | {(dt - prev).total_seconds() / 3600:.2f} h")
        prev = dt
