import re
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
SRC, OUT = ROOT / "src/modelo/extraido_colab", ROOT / "src/modelo"
ALVOS = {55: "bootstrap_5eventos", 56: "auditoria_bootstrap", 61: "delta_teste_c",
         62: "backtest_estrutural", 65: "backtest_multi_evento", 66: "bootstrap_backtest",
         67: "delta_evento_446", 69: "direcao_contagem", 71: "direcao_backtest_v2"}
TROCAS = [("/content/drive/MyDrive/ARCTURUS_ML/", "resultados/"),
          ("/content/telemetria_84580000_2026.json", "data/telemetria_84580000_2026.json"),
          ("/content/split_v3.json", "data/split_v3.json"),
          ("/content/dataset_", "data/dataset_")]
COLAB = re.compile(r"google\.colab|drive\.mount|^\s*[!%]|files\.(download|upload)|/content")
HEADER = '''"""Porte mecanico da cel {n} do CLIMATIK5.ipynb. Corpo original preservado;
so os caminhos mudaram (data/ entradas, resultados/ saidas).
Rode da raiz: python -m src.modelo.{nome}"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
(ROOT / "resultados").mkdir(exist_ok=True)

'''
for n, nome in ALVOS.items():
    src = (SRC / f"cel_{n:02d}.py").read_text(encoding="utf-8")
    for velho, novo in TROCAS:
        src = src.replace(velho, novo)
    sobra = [(i + 1, l.strip()[:60]) for i, l in enumerate(src.splitlines()) if COLAB.search(l)]
    (OUT / f"{nome}.py").write_text(HEADER.format(n=n, nome=nome) + src, encoding="utf-8")
    print(f"ok {nome}.py", f"| ATENCAO: {sobra}" if sobra else "")
