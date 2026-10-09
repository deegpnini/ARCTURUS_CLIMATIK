import json
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
REF, NOVO = ROOT / "data/referencia", ROOT / "resultados"

def difs(a, b, c=""):
    out = []
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            out += [f"{c}/{k}: so de um lado"] if (k not in a or k not in b) else difs(a[k], b[k], f"{c}/{k}")
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b): out.append(f"{c}: tamanho {len(a)} vs {len(b)}")
        else:
            for i, (x, y) in enumerate(zip(a, b)): out += difs(x, y, f"{c}[{i}]")
    else:
        try:
            if abs(float(a) - float(b)) > 1e-6: out.append(f"{c}: {a} vs {b}")
        except (TypeError, ValueError):
            if a != b: out.append(f"{c}: {a} vs {b}")
    return out

for nome in ["backtest_multi_evento.csv", "resultado_teste_c_delta.json", "teste_446_delta.json"]:
    r, n = REF / nome, NOVO / nome
    if not n.exists(): print(f"{nome:32s} ainda nao gerado"); continue
    if nome.endswith(".csv"):
        a, b = pd.read_csv(r), pd.read_csv(n)
        if a.shape != b.shape: print(f"{nome:32s} DIFERE shape {a.shape} vs {b.shape}"); continue
        num = a.select_dtypes("number").columns
        d = float((a[num] - b[num]).abs().max().max())
        txt = [c for c in a.columns if c not in num and not a[c].equals(b[c])]
        print(f"{nome:32s} {'REPRODUZ' if d <= 1e-6 and not txt else 'DIFERE'}  max|dif|={d:.3g}  colunas_texto_difer={txt}")
    else:
        d = difs(json.load(open(r, encoding="utf-8")), json.load(open(n, encoding="utf-8")))
        print(f"{nome:32s} {'REPRODUZ' if not d else 'DIFERE ' + str(d[:3])}")
