import sys
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from sklearn.linear_model import LinearRegression

LIM = float(sys.argv[1]) if len(sys.argv) > 1 else 30.0
BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True)
raw = raw.loc[:, ~raw.columns.duplicated()].sort_index()
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

X = pd.DataFrame(index=g.index)
X["cota"] = c
for m in (15, 30, 60, 180, 360, 720, 1440):
    X[f"cota_lag_{m}m"] = c.shift(m // 15)
X["delta_15m"], X["delta_60m"], X["delta_180m"] = c - c.shift(1), c - c.shift(4), c - c.shift(12)
X["aceleracao_1h"] = X["delta_60m"] - (c.shift(4) - c.shift(8))
r = c.rolling(48, min_periods=40)
X["cota_std_12h"], X["cota_max_12h"], X["cota_min_12h"] = r.std(), r.max(), r.min()
for col in g.columns:
    if col.startswith("chuva_"):
        X[col] = g[col]
h = g.index.hour + g.index.minute / 60
X["sin_hora"], X["cos_hora"] = np.sin(2 * np.pi * h / 24), np.cos(2 * np.pi * h / 24)
d = g.index.dayofyear / 365.0
X["sin_dia_ano"], X["cos_dia_ano"] = np.sin(2 * np.pi * d), np.cos(2 * np.pi * d)

y = (c.shift(-12) - c).rename("y")
D = X.join(y).dropna(subset=["y", "cota"])
tr = D[D.index < "2025-01-01"]
te = D[D.index >= "2025-07-01"]
print("maior cota no treino:", tr["cota"].max(), "| no teste:", te["cota"].max())

b = lgb.Booster(model_file=str(BASE / "modelos" / "modelo_delta_3h_v5_sem_montante.txt"))
dc = ["delta_15m", "delta_60m", "delta_180m"]
lin = LinearRegression().fit(tr[dc].fillna(0), tr["y"])
scores = {
    "tendencia(3x delta_60m)": (3 * te["delta_60m"]).fillna(0).values,
    "linear_deltas": lin.predict(te[dc].fillna(0)),
    "lightgbm_3h": b.predict(te[b.feature_name()]),
}

pos = (te["y"] >= LIM).values
if pos.sum() == 0:
    sys.exit("Nenhum evento com esse limite; tente um valor menor.")
pos_s = pd.Series(pos, index=te.index)
meses = (te.index[-1] - te.index[0]).days / 30.4

def agrupar(ts, gap=pd.Timedelta("6h")):
    out, last = [], None
    for t in ts:
        if last is None or t - last > gap:
            out.append(t)
        last = t
    return out

eventos = agrupar(te.index[pos])
print(f"Evento: +{LIM:.0f} cm em 3h | pontos positivos: {pos.sum()} de {len(pos)} | eventos (>6h entre si): {len(eventos)}")
for nome, s in scores.items():
    for rec in (0.5, 0.8):
        thr = np.quantile(s[pos], 1 - rec)
        al = s >= thr
        al_s = pd.Series(al, index=te.index)
        prec = (al & pos).sum() / max(al.sum(), 1)
        starts = agrupar(te.index[al])
        falsos = sum(not pos_s.loc[t: t + pd.Timedelta("6h")].any() for t in starts)
        det = sum(al_s.loc[t0: t0 + pd.Timedelta("3h")].any() for t0 in eventos)
        print(f"{nome:24s} recall={rec:.0%} limiar={thr:6.1f} precisao={prec:.2f} "
              f"alarmes/mes={len(starts)/meses:5.1f} falsos/mes={falsos/meses:5.1f} eventos={det}/{len(eventos)}")
