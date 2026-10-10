import json
from pathlib import Path

for p in sorted(Path(".").glob("data/**/telemetria_84580000_2026.json")):
    with open(p, encoding="utf-8") as f:
        d = json.load(f)
    its = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
    print(f"\n### {p} | n = {len(its)}")
    tk = next(k for k in its[0] if "data" in k.lower() or "time" in k.lower())
    ck = next(k for k in its[0] if "cota" in k.lower())
    val = [(str(x[tk]).replace("T", " "), x[ck]) for x in its if x.get(ck) not in (None, "")]
    if val:
        print("  max cota:", max(val, key=lambda t: float(t[1])))
    for t, c in val:
        if "2026-09-21 19:30" <= t <= "2026-09-22 03:00":
            print(f"  {t} | cota={c}")
