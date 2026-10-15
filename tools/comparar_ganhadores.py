import pandas as pd
from pathlib import Path
R = Path(__file__).resolve().parents[1]
a = pd.read_csv(R / "data/referencia/backtest_multi_evento.csv")
b = pd.read_csv(R / "resultados/backtest_multi_evento_sem_vazao.csv")
m = a.merge(b, on=["h", "evento"], suffixes=("_ref", "_var"))
m["mudou"] = m["ganhador_ref"] != m["ganhador_var"]
print(len(m), "linhas | ganhador mudou em", int(m["mudou"].sum()))
cols = ["h", "evento", "inicio_ref", "mae_pers_ref", "mae_abs_ref", "mae_delta_ref", "mae_abs_var", "mae_delta_var", "ganhador_ref", "ganhador_var"]
print(m.loc[m["mudou"], cols].round(2).to_string(index=False))
for h, g in m.groupby("h"):
    print(f"{h}: delta ganha ref={int((g['ganhador_ref'] == 'delta').sum())} var={int((g['ganhador_var'] == 'delta').sum())}"
          f" | MAE delta ref={g['mae_delta_ref'].mean():.3f} var={g['mae_delta_var'].mean():.3f}")
