import os, subprocess, sys
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
MOD = ROOT / "src/modelo"
VELHO_CSV = "backtest_multi_evento.csv"
NOVO_CSV = "backtest_multi_evento_sem_vazao.csv"
FEATS = "feats = [c for c in df.columns if c not in ('timestamp', target_abs)]"

def gerar(origem, destino, tira_vazao):
    s = (MOD / origem).read_text(encoding="utf-8")
    if tira_vazao:
        assert s.count(FEATS) == 1, f"{origem}: linha de features achada {s.count(FEATS)}x"
        s = s.replace(FEATS, FEATS.replace("target_abs)", "target_abs, 'vazao')"))
    n = s.count(VELHO_CSV)
    assert n >= 1, f"{origem}: nome do CSV nao encontrado"
    (MOD / destino).write_text(s.replace(VELHO_CSV, NOVO_CSV), encoding="utf-8")
    print(f"ok {destino} (CSV trocado em {n} lugar(es))")

gerar("backtest_multi_evento.py", "_variante_bt_sem_vazao.py", True)
gerar("bootstrap_backtest.py", "_variante_boot_sem_vazao.py", False)

env = dict(os.environ, PYTHONUTF8="1")
for mod in ("_variante_bt_sem_vazao", "_variante_boot_sem_vazao"):
    r = subprocess.run([sys.executable, "-m", f"src.modelo.{mod}"], cwd=ROOT, env=env,
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    print(f"\n===== {mod} (codigo {r.returncode}) =====")
    print((r.stdout or "")[-3500:])
    if r.returncode:
        print((r.stderr or "")[-1500:]); sys.exit(1)

ref = pd.read_csv(ROOT / "data/referencia" / VELHO_CSV)
var = pd.read_csv(ROOT / "resultados" / NOVO_CSV)
print("\n===== REFERENCIA x SEM VAZAO =====")
print("colunas:", list(ref.columns))
print("shape:", ref.shape, "x", var.shape)
if ref.shape == var.shape:
    num = [c for c in ref.select_dtypes("number").columns if c in var.columns][:25]
    out = pd.DataFrame({"ref_media": ref[num].mean(), "var_media": var[num].mean()})
    out["dif_%"] = (100 * (out["var_media"] - out["ref_media"]) / out["ref_media"].abs()).round(1)
    print(out.round(3).to_string())
print("\nprimeiras linhas da referencia:")
print(ref.head(3).to_string())
