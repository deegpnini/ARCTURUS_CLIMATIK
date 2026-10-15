from pathlib import Path
import numpy as np
import pandas as pd

R = Path(__file__).resolve().parents[1]
def P(t): return R / "resultados" / f"backtest_multi_evento_{t}.csv"
PARES = [(R / "data/referencia/backtest_multi_evento.csv", P("sem_vazao")),
         (P("seed11"), P("sv_seed11")), (P("seed22"), P("sv_seed22")), (P("seed33"), P("sv_seed33"))]
fr = []
for k, (a, b) in enumerate(PARES):
    A = pd.read_csv(a)[["h", "evento", "inicio", "n", "mae_delta"]]
    B = pd.read_csv(b)[["h", "evento", "mae_delta"]]
    m = A.merge(B, on=["h", "evento"], suffixes=("_com", "_sem"))
    m["dif"] = m["mae_delta_sem"] - m["mae_delta_com"]
    m["par"] = k
    fr.append(m)
D = pd.concat(fr)
E = D.groupby(["h", "evento"]).agg(inicio=("inicio", "first"), n=("n", "first"), dif=("dif", "mean"),
                                   pares_pior=("dif", lambda x: int((x > 0).sum()))).reset_index()
rng = np.random.default_rng(0)
def ic(x):
    x = np.asarray(x)
    b = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(10000)]
    return np.percentile(b, [2.5, 97.5])

for h, g in E.groupby("h"):
    x = g["dif"].values
    lo, hi = ic(x)
    g2 = g[g["evento"] != 14]
    lo2, hi2 = ic(g2["dif"].values)
    e14 = g.loc[g["evento"] == 14, "dif"].iloc[0]
    print(f"\n===== {h} (dif = MAE delta SEM vazao - COM vazao; positivo = piora sem vazao) =====")
    print(f"27 eventos : media {x.mean():+.3f} cm  IC95 [{lo:+.3f}, {hi:+.3f}]  | piora em {int((x > 0).sum())}/27 eventos")
    print(f"sem ev. 14 : media {g2['dif'].mean():+.3f} cm  IC95 [{lo2:+.3f}, {hi2:+.3f}]  | piora em {int((g2['dif'] > 0).sum())}/26 eventos")
    print(f"evento 14  : dif {e14:+.2f} cm = {100 * (e14 / 27) / x.mean():.0f}% da media dos 27")
    cols = ["evento", "inicio", "n", "dif", "pares_pior"]
    print("maiores pioras:");  print(g.sort_values("dif", ascending=False).head(4)[cols].round(2).to_string(index=False))
    print("maiores melhoras:"); print(g.sort_values("dif").head(2)[cols].round(2).to_string(index=False))
