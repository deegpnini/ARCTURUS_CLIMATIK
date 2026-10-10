import json, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]

print("== 1. linhas que montam features ou citam vazao ==")
arqs = set()
for pat in ("tools/*.py", "src/modelo/*.py", "src/**/*.py"):
    arqs |= set(ROOT.glob(pat))
for f in sorted(arqs):
    rel = f.relative_to(ROOT).as_posix()
    if "extraido_colab" in rel or "/_variante_" in rel:
        continue
    for i, l in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
        if re.search(r"feats\s*=|feature_cols|vazao|drop\(columns", l):
            print(f"{rel}:{i}: {l.strip()[:140]}")

print("\n== 2. manifesto_producao.json ==")
for mp in ROOT.rglob("manifesto_producao.json"):
    if "_backup" in mp.parts:
        continue
    d = json.load(open(mp, encoding="utf-8"))
    print(mp.relative_to(ROOT).as_posix(), "| chaves:", list(d.keys()))
    def walk(o, path=""):
        if isinstance(o, dict):
            for k, v in o.items():
                walk(v, f"{path}/{k}")
        elif isinstance(o, list) and o and all(isinstance(x, str) for x in o) and "feat" in path.lower():
            print(f"  {path}: {len(o)} features | vazao presente: {'vazao' in o}")
    walk(d)

print("\n== 3. colunas do dataset_1h ==")
cols = pd.read_csv(ROOT / "data/dataset_1h.csv", nrows=1).columns.tolist()
print(len(cols), "colunas (27 features + timestamp + target = 29?):", cols)

print("\n== 4. patch seguro no testador ==")
t = ROOT / "tools/testar_reprodutibilidade.py"
s = t.read_text(encoding="utf-8")
if "vazao" in s:
    print("o testador ja cita vazao; nao mexo")
else:
    pat = re.compile(r"(feats\s*=\s*\[\s*c\s+for\s+c\s+in\s+\w+\.columns\s+if\s+c\s+not\s+in\s*[\(\[])([^\)\]]*)([\)\]])")
    n = len(pat.findall(s))
    if n == 1:
        s2 = pat.sub(lambda m: m.group(1) + m.group(2).rstrip().rstrip(",") + ', "vazao"' + m.group(3), s, count=1)
        t.write_text(s2, encoding="utf-8")
        print("patch aplicado em tools/testar_reprodutibilidade.py")
    else:
        print(f"padrao nao encontrado (ocorrencias={n}). Nao alterei nada; veja a secao 1")
