from pathlib import Path
import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[1]
RES = R / "resultados"
SEM = {"padrao": "sem_vazao", "semente 11": "sv_seed11", "semente 22": "sv_seed22", "semente 33": "sv_seed33"}
COMP = [R / "data/referencia/backtest_multi_evento.csv"] + [RES / f"backtest_multi_evento_seed{s}.csv" for s in (11, 22, 33)]
LIM_ABS = {"1h": 0.10, "3h": 0.14, "6h": 0.24}
LIM_PER = {"1h": 0.10, "3h": 0.20, "6h": 0.34}

def ved(g, col, lim):
    x = g[col] - g["mae_delta"]
    return int((x > lim).sum()), int((x.abs() <= lim).sum()), int((x < -lim).sum())
def fmt(v): return f"{v[0]}/{v[1]}/{v[2]}"

sem = {n: pd.read_csv(RES / f"backtest_multi_evento_{t}.csv") for n, t in SEM.items()}
L = ["# Resultados do modelo de producao (26 features, sem `vazao`)", "",
     "Backtest leave-one-event-out: 27 eventos da estacao 84580000, 4 execucoes (treino padrao e sementes 11, 22, 33). "
     "V/E/D = vitorias/empates/derrotas do delta, com margem de empate por horizonte "
     "(persistencia 0,10/0,20/0,34 cm; absoluto 0,10/0,14/0,24 cm).", "",
     "| Horizonte | Delta vs persistencia (vitorias de 27) | Delta vs absoluto (vitorias de 27) | MAE medio delta (cm) | MAE medio persistencia (cm) | MAE medio absoluto (cm) |",
     "|---|---|---|---|---|---|"]
for h in ("1h", "3h", "6h"):
    g = [d[d.h == h] for d in sem.values()]
    vp = [ved(x, "mae_pers", LIM_PER[h])[0] for x in g]
    va = [ved(x, "mae_abs", LIM_ABS[h])[0] for x in g]
    md = [x.mae_delta.mean() for x in g]; ma = [x.mae_abs.mean() for x in g]
    L.append(f"| {h} | {min(vp)}-{max(vp)} | {min(va)}-{max(va)} | {min(md):.2f}-{max(md):.2f} | {g[0].mae_pers.mean():.2f} | {min(ma):.2f}-{max(ma):.2f} |")

L += ["", "Execucao padrao (V/E/D):"]
for h in ("1h", "3h", "6h"):
    x = sem["padrao"][sem["padrao"].h == h]
    L.append(f"- {h}: vs persistencia {fmt(ved(x, 'mae_pers', LIM_PER[h]))} | vs absoluto {fmt(ved(x, 'mae_abs', LIM_ABS[h]))}")

rng = np.random.default_rng(0)
L += ["", "## Custo de remover `vazao` (4 pares com/sem, mesma semente)", ""]
for h in ("1h", "3h", "6h"):
    difs = []
    for pcom, dsem in zip(COMP, sem.values()):
        a = pd.read_csv(pcom); a = a[a.h == h].set_index("evento").mae_delta
        b = dsem[dsem.h == h].set_index("evento").mae_delta
        difs.append(b - a)
    x = pd.concat(difs, axis=1).mean(axis=1).values
    bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(10000)]
    lo, hi = np.percentile(bs, [2.5, 97.5])
    L.append(f"- {h}: {x.mean():+.3f} cm no MAE do delta (sem - com), IC95% [{lo:+.3f}, {hi:+.3f}]; positivo = piora sem vazao")

ref = pd.read_csv(COMP[0]); pic = ref[ref.h == "1h"].pico.values
p95, p99 = np.percentile(pic, [95, 99])
L += ["", "## Limitacoes", "",
      f"- Uma estacao e 27 eventos. Acima do P95 dos picos ({p95:.0f} cm) ha {int((pic > p95).sum())} eventos e acima do P99 ({p99:.0f} cm) {int((pic > p99).sum())}: sem inferencia para eventos severos.",
      "- A contagem de vitorias oscila 3 a 4 eventos so por semente; por isso relatamos faixas.",
      "- O maior pico do treino e 312 cm. O evento de 22/09/2026 (446 cm na primeira leitura apos um intervalo de 4h15 sem dados, ja em recessao) esta fora dessa faixa; o pico real e desconhecido (>= 446 cm).",
      "- O teste do 446 usou poucas features e e um unico caso."]
out = R / "docs/RESULTADOS_26_features.md"
out.write_text("\n".join(L) + "\n", encoding="utf-8")
print("\n".join(L)); print(f"\n[OK] {out}")
