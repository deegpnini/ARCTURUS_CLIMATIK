import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
a = json.load(open(ROOT / "data/resultado_lightgbm.json", encoding="utf-8"))
b = json.load(open(ROOT / "resultados/resultado_lightgbm.json", encoding="utf-8"))
ok = True
for h in a:
    for k, va in a[h].items():
        vb = b[h].get(k)
        try:
            d = abs(float(va) - float(vb))
        except (TypeError, ValueError):
            d = 0 if va == vb else None
        marca = "ok" if d is not None and d <= 0.01 else "DIFERE"
        ok &= (marca == "ok")
        print(f"{h} {k:15s} colab={va}  win={vb}  {marca}")
print("REPRODUZ" if ok else "NAO REPRODUZ")
