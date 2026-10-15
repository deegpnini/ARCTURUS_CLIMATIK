import os, re, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src/modelo"
src = (MOD / "backtest_multi_evento.py").read_text(encoding="utf-8")
pat = re.compile(r"^(\s*)params\s*=\s*\{", re.M)
if len(pat.findall(src)) != 1 or "'seed'" in src or '"seed"' in src:
    print("padrao de params inesperado. Linhas com 'params' ou 'seed':")
    for i, l in enumerate(src.splitlines(), 1):
        if "params" in l or "seed" in l:
            print(i, l.strip()[:120])
    sys.exit(1)

SEEDS = [11, 22]
env = dict(os.environ, PYTHONUTF8="1")
for sd in SEEDS:
    s = pat.sub(lambda m: f"{m.group(1)}params = {{'seed': {sd}, 'bagging_seed': {sd}, 'feature_fraction_seed': {sd}, ", src, count=1)
    assert "backtest_multi_evento.csv" in s
    s = s.replace("backtest_multi_evento.csv", f"backtest_multi_evento_seed{sd}.csv")
    mod = f"_variante_seed{sd}"
    (MOD / f"{mod}.py").write_text(s, encoding="utf-8")
    print(f"rodando semente {sd} (com vazao) ...", flush=True)
    r = subprocess.run([sys.executable, "-m", f"src.modelo.{mod}"], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print((r.stderr or "")[-1500:]); sys.exit(1)

runs = {"ref (com vazao)": pd.read_csv(ROOT / "data/referencia/backtest_multi_evento.csv"),
        "sem vazao": pd.read_csv(ROOT / "resultados/backtest_multi_evento_sem_vazao.csv")}
for sd in SEEDS:
    runs[f"semente {sd} (com vazao)"] = pd.read_csv(ROOT / f"resultados/backtest_multi_evento_seed{sd}.csv")

print(f"\n{'versao':26} {'h':3} {'delta<abs':>9} {'delta<pers':>10} {'MAE delta':>9} {'MAE abs':>8}")
for nome, d in runs.items():
    for h, g in d.groupby("h"):
        print(f"{nome:26} {h:3} {int((g.mae_delta < g.mae_abs).sum()):9d} {int((g.mae_delta < g.mae_pers).sum()):10d} {g.mae_delta.mean():9.3f} {g.mae_abs.mean():8.3f}")

print("\nganhadores que mudam entre versoes (de 81):")
base = runs["ref (com vazao)"]
for nome, d in runs.items():
    if nome.startswith("ref"):
        continue
    m = base.merge(d, on=["h", "evento"], suffixes=("_a", "_b"))
    print(f"  ref x {nome:26}: {int((m.ganhador_a != m.ganhador_b).sum())}")
