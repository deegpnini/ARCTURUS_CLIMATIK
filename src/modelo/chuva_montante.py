import requests
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# Coordenadas das estações a montante (cabeceiras do Tubarão)
estacoes = {
    "Orleans": (-28.36, -49.29),
    "Rio Fortuna": (-28.13, -49.10),
    "Bom Jardim da Serra": (-28.34, -49.62),
    "Lauro Müller": (-28.39, -49.40),
}

# Baixar a chuva diária (últimos 30 dias) via Open-Meteo (ERA5)
# (O Open-Meteo tem dados históricos de chuva, com latência de ~5 dias)
dfs = []
for nome, (lat, lon) in estacoes.items():
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=2026-09-01&end_date=2026-10-30&daily=precipitation_sum&timezone=America%2FSao_Paulo"
    r = requests.get(url)
    data = r.json()
    df = pd.DataFrame({
        "data": pd.to_datetime(data["daily"]["time"]),
        "chuva_mm": data["daily"]["precipitation_sum"],
        "estacao": nome
    })
    dfs.append(df)

df_chuva = pd.concat(dfs)
df_chuva = df_chuva.pivot(index="data", columns="estacao", values="chuva_mm")
df_chuva["chuva_montante_24h"] = df_chuva.sum(axis=1)
df_chuva["chuva_montante_72h"] = df_chuva["chuva_montante_24h"].rolling(3).sum()
df_chuva["chuva_montante_7d"] = df_chuva["chuva_montante_24h"].rolling(7).sum()

df_chuva.to_csv(BASE / "data" / "chuva_montante.csv")
print(f"✅ Chuva a montante salva em: data/chuva_montante.csv")
print(df_chuva.tail())
