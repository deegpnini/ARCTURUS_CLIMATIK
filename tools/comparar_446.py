import json
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
a = json.load(open(ROOT / "data/referencia/teste_446_delta.json", encoding="utf-8"))
b = json.load(open(ROOT / "resultados/teste_446_delta.json", encoding="utf-8"))
print(f"{'h':3} {'campo':12} {'referencia':>11} {'novo':>11}")
for h in a:
    for k in ("alvo_obs", "pred_delta", "err_persist", "err_abs", "err_delta"):
        x, y = float(a[h][k]), float(b[h][k])
        print(f"{h:3} {k:12} {x:11.3f} {y:11.3f}  {'igual' if abs(x - y) < 1e-6 else 'MUDOU'}")
for h in b:
    ep, ed = float(b[h]["err_persist"]), float(b[h]["err_delta"])
    print(f"{h}: ganho do delta sobre a persistencia = {100 * (ep - ed) / ep:.1f}%")
