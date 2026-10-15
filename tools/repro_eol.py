import hashlib, shutil, subprocess, sys, tempfile
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
ARQS = ["tools/treinar_producao.py", "data/dataset_1h.csv", "data/dataset_3h.csv", "data/dataset_6h.csv",
        "data/split_v3.json", "resultados/manifesto_loeo_v2.json"]
def h(b): return hashlib.sha256(b).hexdigest()[:16]
def hs(b): return h(b.replace(b"\r", b""))
tmp = Path(tempfile.mkdtemp(prefix="arcturus_eol_"))
try:
    for rel in ARQS:
        d = tmp / rel; d.parent.mkdir(parents=True, exist_ok=True); shutil.copy2(ROOT / rel, d)
    (tmp / "modelos").mkdir()
    r = subprocess.run([sys.executable, "tools/treinar_producao.py"], cwd=tmp, capture_output=True, text=True, errors="replace")
    print("codigo de saida:", r.returncode)
    if r.returncode:
        print((r.stderr or r.stdout)[-1500:]); sys.exit(1)
    print(f"{'h':3} {'run bruto':17} {'repo bruto':17} {'run sem CR':17} {'repo sem CR':17} {'CR run':>7} {'CR repo':>8}")
    for hz in ("1h", "3h", "6h"):
        a = (tmp / f"modelos/modelo_delta_{hz}.txt").read_bytes()
        b = (ROOT / f"modelos/modelo_delta_{hz}.txt").read_bytes()
        cra, crb = a.count(b"\r"), b.count(b"\r")
        print(f"{hz:3} {h(a):17} {h(b):17} {hs(a):17} {hs(b):17} {cra:7d} {crb:8d}")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
