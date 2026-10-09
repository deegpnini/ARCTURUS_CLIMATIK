import ast, builtins, re
from pathlib import Path
D = Path("src/modelo/extraido_colab")

def parse(p):
    linhas = ["pass" if l.lstrip().startswith(("!", "%")) else l
              for l in p.read_text(encoding="utf-8").splitlines()]
    try: return ast.parse("\n".join(linhas))
    except SyntaxError: return None

cells = {}
for p in sorted(D.glob("cel_*.py")):
    t = parse(p)
    if t: cells[int(p.stem[4:])] = (p, t)

def stores(t):
    s = set()
    for n in ast.walk(t):
        if isinstance(n, ast.Name) and isinstance(n.ctx, (ast.Store, ast.Del)): s.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.ClassDef)): s.add(n.name)
        elif isinstance(n, ast.arg): s.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            for a in n.names: s.add((a.asname or a.name).split(".")[0])
        elif isinstance(n, ast.ExceptHandler) and n.name: s.add(n.name)
    return s

def loads(t):
    return {n.id for n in ast.walk(t) if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load)}

ARQ = re.compile(r'["\']([^"\']*\.(?:csv|json|jsonl|pkl|joblib|txt))["\']')
for n in [53, 55, 56, 61, 62, 65, 66, 67, 69, 71]:
    if n not in cells: print(f"\n### cel {n}: nao parseia"); continue
    p, t = cells[n]; txt = p.read_text(encoding="utf-8")
    titulo = next((l.strip("# ").strip() for l in txt.splitlines()[1:6] if l.startswith("#") and "====" not in l), "")
    print(f"\n### cel {n} ({len(txt)} chars) {titulo}")
    print("  arquivos:", sorted(set(ARQ.findall(txt))))
    print("  /content nas linhas:", [i + 1 for i, l in enumerate(txt.splitlines()) if "/content" in l])
    for nome in sorted(loads(t) - stores(t) - set(dir(builtins))):
        defs = [m for m in cells if m < n and nome in stores(cells[m][1])]
        print(f"  usa {nome:20s} <- cel {defs[-1] if defs else 'NENHUMA'}")
