import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True).sort_index()
raw = raw.loc[:, ~raw.columns.duplicated()]
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

X = pd.DataFrame(index=g.index)
X["cota"] = c
X["delta_60m"] = c - c.shift(4)

ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
X["bacia_6h"] = media.rolling(6, min_periods=6).sum().reindex(g.index, method="ffill")

X["y_6h"] = (c.shift(-24) - c)
D = X.dropna(subset=["y_6h"])
total = len(D)
eventos_reais = (D["y_6h"] > 30).sum()

print(f"Total de linhas: {total} | Eventos reais (subida > 30cm em 6h): {eventos_reais}")
print(f"\n{'Limiar (delta)':>15} | {'Disparos':>8} | {'Acertos':>8} | {'Falsos':>8} | {'Precisão':>8} | {'Recall':>8}")
print("-" * 75)

for limiar in [20, 25, 30, 35, 40, 45, 50]:
    detector = (D["delta_60m"] > limiar) | (D["bacia_6h"] > 50) | (D["cota"] > 300)
    disparos = detector.sum()
    acertos = (detector & (D["y_6h"] > 30)).sum()
    falsos = disparos - acertos
    precisao = acertos / max(disparos, 1) * 100
    recall = acertos / max(eventos_reais, 1) * 100
    print(f"{limiar:>15} | {disparos:>8} | {acertos:>8} | {falsos:>8} | {precisao:>7.1f}% | {recall:>7.1f}%")
