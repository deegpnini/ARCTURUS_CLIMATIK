import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True)
raw = raw.loc[:, ~raw.columns.duplicated()].sort_index()
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()

cc = pd.DataFrame(json.load(open(BASE / "cache" / "ana_historico_84580000.json"))["items"])
cc["t"] = pd.to_datetime(cc["Data_Hora_Medicao"])
cc = cc.drop_duplicates("t", keep="last").set_index("t").sort_index()
cc["cota"] = pd.to_numeric(cc["Cota_Adotada"], errors="coerce")
cc["chuva"] = pd.to_numeric(cc["Chuva_Adotada"], errors="coerce")

ov = g.index.intersection(cc.index)
dif = (g.loc[ov, "cota"] - cc.loc[ov, "cota"]).abs()
print(f"dataset x cache: {len(ov)} instantes em comum | ambos com cota: {int(dif.notna().sum())} | dif media {dif.mean():.2f} cm | max {dif.max():.1f} cm")

idx = pd.date_range(g.index.min(), cc.index.max(), freq="15min")
novo = np.asarray(idx > g.index.max())
c = g["cota"].reindex(idx)
r15 = g["chuva_15m"].reindex(idx)
c[novo] = cc["cota"].reindex(idx[novo]).values
r15[novo] = cc["chuva"].reindex(idx[novo]).values

X = pd.DataFrame(index=idx)
X["cota"] = c
for m in (15, 30, 60, 180, 360, 720, 1440):
    X[f"cota_lag_{m}m"] = c.shift(m // 15)
X["delta_15m"], X["delta_60m"], X["delta_180m"] = c - c.shift(1), c - c.shift(4), c - c.shift(12)
X["aceleracao_1h"] = X["delta_60m"] - (c.shift(4) - c.shift(8))
r = c.rolling(48, min_periods=40)
X["cota_std_12h"], X["cota_max_12h"], X["cota_min_12h"] = r.std(), r.max(), r.min()
for w in (15, 60, 180, 360, 720, 1440, 2880):
    n = w // 15
    k = f"chuva_{w}m"
    X[k] = r15.rolling(n, min_periods=int(np.ceil(0.9 * n))).sum()
    if k in g.columns:
        o = g[k].reindex(idx)
        ok = o.notna() & X[k].notna()
        print(f"{k} recalculada x dataset: dif media {(o[ok] - X.loc[ok, k]).abs().mean():.3f} mm | NaN so no dataset {int((o.isna() & X[k].notna()).sum())} | NaN so no recalculo {int((o.notna() & X[k].isna()).sum())}")
hh = idx.hour + idx.minute / 60
X["sin_hora"], X["cos_hora"] = np.sin(2 * np.pi * hh / 24), np.cos(2 * np.pi * hh / 24)
dd = idx.dayofyear / 365.0
X["sin_dia_ano"], X["cos_dia_ano"] = np.sin(2 * np.pi * dd), np.cos(2 * np.pi * dd)
base = list(X.columns)

ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
media = ch.mean(axis=1)
for k in (1, 3, 6, 12, 24, 48):
    X[f"bacia_{k}h"] = media.rolling(k, min_periods=k).sum().reindex(idx, method="ffill")
s3 = ch.rolling(3, min_periods=3).sum()
X["bacia_max3h"] = s3.max(axis=1).reindex(idx, method="ffill")
X["bacia_pontos_chovendo"] = (s3 > 5).sum(axis=1).reindex(idx, method="ffill")
com = list(X.columns)

def treinar(cols, tr, va, seed):
    P = dict(objective="regression", learning_rate=0.03, num_leaves=15, min_data_in_leaf=100,
             feature_fraction=0.8, bagging_fraction=0.8, bagging_freq=1, seed=seed, verbose=-1)
    dtr = lgb.Dataset(tr[cols], tr["y"])
    dva = lgb.Dataset(va[cols], va["y"], reference=dtr)
    return lgb.train(P, dtr, 3000, valid_sets=[dva], callbacks=[lgb.early_stopping(100, verbose=False)])

T0 = pd.date_range("2026-09-21 19:00", "2026-09-21 19:45", freq="15min")
corte = T0[0]
t_fim = pd.Timestamp("2026-09-22 00:00")
print("\nsubida real de cada emissao ate 00:00:", {f"{t:%H:%M}": float(c.loc[t_fim] - c.loc[t]) for t in T0})

for H, n in ((1, 4), (3, 12), (6, 24)):
    y = (c.shift(-n) - c).rename("y")
    D = X.join(y).dropna(subset=["y", "cota"])
    D = D[D.index + pd.Timedelta(hours=H) <= corte]
    tr, va = D[D.index < "2026-03-01"], D[D.index >= "2026-03-01"]
    if len(va) < 500:
        cut = D.index[int(len(D) * 0.85)]
        tr, va = D[D.index < cut], D[D.index >= cut]
    P = {}
    for nome, cols in (("so_ponto", base), ("com_bacia", com)):
        ps = []
        for s in range(3):
            b = treinar(cols, tr, va, s)
            ps.append(b.predict(X.loc[T0, cols], num_iteration=b.best_iteration))
        P[nome] = np.mean(ps, axis=0)
    obs = y.reindex(T0)
    print(f"\n=== {H}h | treino {len(tr)} val {len(va)} | maior |delta| visto: {D['y'].abs().max():.0f} cm ===")
    for i, t in enumerate(T0):
        o = obs.iloc[i]
        txt = f"{o:+.0f}" if pd.notna(o) else "sem dado (lacuna)"
        cota_t, d60 = X.loc[t, "cota"], X.loc[t, "delta_60m"]
        print(f"emitida {t:%H:%M} cota={cota_t:.0f} delta_60m={d60:+.0f} | observado={txt} | so_ponto={P['so_ponto'][i]:+.1f} com_bacia={P['com_bacia'][i]:+.1f}")

print("\nChuva da bacia (Open-Meteo, mm/h; hora terminando em t):")
ctx = pd.DataFrame({"media": media, "max_pontos": ch.max(axis=1)}).loc["2026-09-21 12:00":"2026-09-22 02:00"]
print(ctx.round(1).to_string())
