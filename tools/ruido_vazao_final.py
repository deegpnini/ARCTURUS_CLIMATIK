import re, subprocess, sys, os
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src/modelo"
RES = ROOT / "resultados"
REF = ROOT / "data/referencia/backtest_multi_evento.csv"
def P(tag): return RES / f"backtest_multi_evento_{tag}.csv"

# ---------- parte 1: as duas regras de contagem (so le CSV) ----------
LIM_ABS = {"1h": 0.10, "3h": 0.14, "6h": 0.24}
LIM_PER = {"1h": 0.10, "3h": 0.20, "6h": 0.34}
ESP = {"ref": {"abs": {"1h": (19,4,4), "3h": (18,4,5), "6h": (20,4,3)}, "per": {"1h": (26,0,1), "3h": (26,0,1), "6h": (24,1,2)}},
       "sem_vazao": {"abs": {"1h": (19,4,4), "3h": (22,1,4), "6h": (16,6,5)}, "per": {"1h": (26,0,1), "3h": (26,0,1), "6h": (23,2,2)}}}
ARQ = {"ref": REF, "sem_vazao": P("sem_vazao"), "seed11": P("seed11"), "seed22": P("seed22")}

def wel(g, col, lim):
    x = g[col] - g["mae_delta"]
    return (int((x > lim).sum()), int((x.abs() <= lim).sum()), int((x < -lim).sum()))

print("== 1. REGRA COM MARGEM DE EMPATE (V/E/D) x contagem estrita ==")
for nome, path in ARQ.items():
    d = pd.read_csv(path)
    for h, g in d.groupby("h"):
        a, p = wel(g, "mae_abs", LIM_ABS[h]), wel(g, "mae_pers", LIM_PER[h])
        estrito = int((g.mae_delta < g.mae_abs).sum())
        marca = ""
        if nome in ESP:
            marca = "OK" if (a == ESP[nome]["abs"][h] and p == ESP[nome]["per"][h]) else f"DIFERE (esperado abs {ESP[nome]['abs'][h]}, pers {ESP[nome]['per'][h]})"
        print(f"{nome:10} {h}: vs abs {a} | vs pers {p} | estrito delta<abs = {estrito} {marca}")

# ---------- parte 2: execucoes que faltam ----------
FEATS = "feats = [c for c in df.columns if c not in ('timestamp', target_abs)]"
src0 = (MOD / "backtest_multi_evento.py").read_text(encoding="utf-8")
pat = re.compile(r"^(\s*)params\s*=\s*\{", re.M)
assert len(pat.findall(src0)) == 1 and src0.count(FEATS) == 1 and "backtest_multi_evento.csv" in src0, "padrao inesperado no backtest"
JOBS = [("seed33", 33, False), ("sv_seed11", 11, True), ("sv_seed22", 22, True), ("sv_seed33", 33, True)]
env = dict(os.environ, PYTHONUTF8="1")
for tag, sd, sv in JOBS:
    if P(tag).exists():
        print("ja existe:", P(tag).name); continue
    s = pat.sub(lambda m: f"{m.group(1)}params = {{'seed': {sd}, 'bagging_seed': {sd}, 'feature_fraction_seed': {sd}, ", src0, count=1)
    if sv:
        s = s.replace(FEATS, FEATS.replace("target_abs)", "target_abs, 'vazao')"))
    s = s.replace("backtest_multi_evento.csv", f"backtest_multi_evento_{tag}.csv")
    mod = f"_variante_{tag}"
    (MOD / f"{mod}.py").write_text(s, encoding="utf-8")
    print(f"rodando {tag} (semente {sd}, {'SEM' if sv else 'COM'} vazao) ...", flush=True)
    r = subprocess.run([sys.executable, "-m", f"src.modelo.{mod}"], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print((r.stderr or "")[-1500:]); sys.exit(1)

# ---------- parte 3: criterio ----------
COM = {"ref": REF, "seed11": P("seed11"), "seed22": P("seed22"), "seed33": P("seed33")}
SEM = {"sem_padrao": P("sem_vazao"), "sv11": P("sv_seed11"), "sv22": P("sv_seed22"), "sv33": P("sv_seed33")}
def metr(path):
    d = pd.read_csv(path)
    return {h: (int((g.mae_delta < g.mae_abs).sum()), float(g.mae_delta.mean())) for h, g in d.groupby("h")}
M = {g: {n: metr(p) for n, p in grp.items()} for g, grp in (("COM vazao", COM), ("SEM vazao", SEM))}
print("\n== 3. TABELA POR EXECUCAO (delta<abs estrito | MAE medio do delta) ==")
for g, runs in M.items():
    for n, m in runs.items():
        print(f"{g:10} {n:11}", " | ".join(f"{h}: {m[h][0]:2d} {m[h][1]:.3f}" for h in ("1h", "3h", "6h")))
print("\n== CRITERIO: as faixas min-max se sobrepoem? ==")
for h in ("1h", "3h", "6h"):
    for i, nome in ((0, "delta<abs"), (1, "MAE delta")):
        f = {g: [m[h][i] for m in runs.values()] for g, runs in M.items()}
        a, b = min(f["COM vazao"]), max(f["COM vazao"])
        c, d = min(f["SEM vazao"]), max(f["SEM vazao"])
        ok = max(a, c) <= min(b, d)
        print(f"{h} {nome:9}: COM [{a:.3f}, {b:.3f}]  SEM [{c:.3f}, {d:.3f}]  -> {'SOBREPOE' if ok else 'NAO SOBREPOE'}")
