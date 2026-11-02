import numpy as np
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
raw = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True).sort_index()
raw = raw.loc[:, ~raw.columns.duplicated()]
raw = raw[~raw.index.duplicated(keep="last")]
g = raw.resample("15min").last()
c = g["cota"]

# Features do detector
X = pd.DataFrame(index=g.index)
X["cota"] = c
X["delta_60m"] = c - c.shift(4)

# Chuva da bacia
ch = pd.read_csv(BASE / "data" / "chuva_bacia_openmeteo.csv", index_col=0, parse_dates=True).sort_index()
ch = ch.drop(columns=["braco_norte"], errors="ignore")
media = ch.mean(axis=1)
X["bacia_6h"] = media.rolling(6, min_periods=6).sum().reindex(g.index, method="ffill")

# Alvo: delta de 6h (para saber se o detector acertou)
X["y_6h"] = (c.shift(-24) - c)

# Regra do detector
# O detector dispara quando:
# delta_60m > 20 cm/h OU bacia_6h > 50 mm OU cota > 300 cm
X["detector"] = (X["delta_60m"] > 20) | (X["bacia_6h"] > 50) | (X["cota"] > 300)
X["detector"] = X["detector"].fillna(False)

# Quantos disparos e quantos foram "acertos"?
D = X.dropna(subset=["y_6h"])
total = len(D)
disparos = D["detector"].sum()
acertos = ((D["detector"]) & (D["y_6h"] > 30)).sum()
falsos = disparos - acertos

print(f"Total de linhas: {total}")
print(f"Disparos do detector: {disparos} ({disparos/total*100:.2f}%)")
print(f"Acertos (subida real > 30 cm em 6h): {acertos}")
print(f"Falsos alarmes: {falsos}")
print(f"Precisão do detector: {acertos/disparos*100:.1f}%" if disparos > 0 else "Sem disparos")

# Detalhamento por evento
print("\n--- Detalhamento dos disparos ---")
D_disparos = D[D["detector"]]
if len(D_disparos) > 0:
    # Agrupar disparos por evento (separados por mais de 6h)
    D_disparos = D_disparos.copy()
    D_disparos["grupo"] = (D_disparos.index.to_series().diff() > pd.Timedelta("6h")).cumsum()
    for grupo, dados in D_disparos.groupby("grupo"):
        inicio = dados.index.min()
        fim = dados.index.max()
        max_subida = dados["y_6h"].max()
        print(f"  Evento {grupo}: {inicio:%Y-%m-%d %H:%M} a {fim:%H:%M} | Subida real: {max_subida:+.0f} cm")
