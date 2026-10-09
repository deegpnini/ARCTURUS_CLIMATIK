from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
src = (ROOT / "src/modelo/extraido_colab/cel_50.py").read_text(encoding="utf-8")

HEADER = '''"""Porte mecanico da cel 50 do CLIMATIK5.ipynb (persistencia vs LightGBM absoluto).
Corpo original preservado; so imports, caminhos e encoding foram alterados."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PASTA = ROOT / "resultados"
PASTA.mkdir(exist_ok=True)

'''

trocas = [
    ('open("/content/split_v3.json")', 'open(DATA / "split_v3.json", encoding="utf-8")'),
    ('pd.read_csv(f"/content/dataset_{h}.csv")', 'pd.read_csv(DATA / f"dataset_{h}.csv")'),
]
for velho, novo in trocas:
    assert src.count(velho) == 1, velho
    src = src.replace(velho, novo)
(ROOT / "src/modelo/benchmark.py").write_text(HEADER + src, encoding="utf-8")
print("ok: src/modelo/benchmark.py")
