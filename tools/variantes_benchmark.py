import json, os, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
base = (ROOT / "src/modelo/benchmark.py").read_text(encoding="utf-8")
A = "feats = [c for c in df.columns if c not in ('timestamp', target)]"
B = "df['timestamp'] = pd.to_datetime(df['timestamp'])"
H = "PASTA.mkdir(exist_ok=True)\n"
for s in (A, B, H):
    assert base.count(s) == 1, s
assert "resultado_lightgbm.json" in base

S1_CODE = '''
def _status1():
    out = set()
    for f in sorted((ROOT / "data/_backup/cache").glob("telemetria_84580000_*.json")):
        d = json.load(open(f, encoding="utf-8"))
        its = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
        for x in its:
            try:
                if float(x.get("Cota_Adotada_Status")) == 1.0:
                    out.add(pd.to_datetime(str(x["Data_Hora_Medicao"]).replace("T", " ")[:19]))
            except (TypeError, ValueError):
                pass
    return out
S1 = _status1()
print("linhas status=1 conhecidas:", len(S1))
'''
VARS = {"sem_vazao": (True, False), "sem_status1": (False, True), "sem_ambos": (True, True)}
res = {"base": json.load(open(ROOT / "resultados/resultado_lightgbm.json", encoding="utf-8"))}
env = dict(os.environ, PYTHONUTF8="1")
for nome, (dv, dst) in VARS.items():
    src = base
    if dv:
        src = src.replace(A, "feats = [c for c in df.columns if c not in ('timestamp', target, 'vazao')]")
    if dst:
        src = src.replace(H, H + S1_CODE)
        src = src.replace(B, B + "\n    df = df[~df['timestamp'].isin(S1)].reset_index(drop=True)")
    src = src.replace("resultado_lightgbm.json", f"resultado_lightgbm_{nome}.json")
    mod = f"_variante_{nome}"
    (ROOT / f"src/modelo/{mod}.py").write_text(src, encoding="utf-8")
    r = subprocess.run([sys.executable, "-m", f"src.modelo.{mod}"], cwd=ROOT, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(nome, "ERRO:\n", r.stderr[-1500:]); continue
    res[nome] = json.load(open(ROOT / f"resultados/resultado_lightgbm_{nome}.json", encoding="utf-8"))
    print("ok", nome)

def ganho(r, h, a, b):
    try: return 100 * (1 - float(r[h][a]) / float(r[h][b]))
    except (TypeError, ValueError, ZeroDivisionError): return float("nan")
print(f"\n{'variante':12} {'h':3} {'MAE lgb':>8} {'MAE pers':>9} {'ganho%':>7} {'ganhoP95%':>9} {'best_it':>7}")
for nome, r in res.items():
    for h in ("1h", "3h", "6h"):
        print(f"{nome:12} {h:3} {float(r[h]['lgb_global']):8.2f} {float(r[h]['persist_global']):9.2f} "
              f"{ganho(r, h, 'lgb_global', 'persist_global'):7.1f} {ganho(r, h, 'lgb_p95', 'persist_p95'):9.1f} {int(r[h]['best_iter']):7d}")
