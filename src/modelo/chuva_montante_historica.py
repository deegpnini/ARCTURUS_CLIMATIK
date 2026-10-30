import requests
import pandas as pd
from pathlib import Path
import time

BASE = Path(__file__).resolve().parents[2]

# Coordenadas das estações a montante
estacoes = {
    "Orleans": (-28.36, -49.29),
    "Rio Fortuna": (-28.13, -49.10),
    "Bom Jardim da Serra": (-28.34, -49.62),
    "Lauro Müller": (-28.39, -49.40),
}

# Baixar a chuva diária (1939-2026) via Open-Meteo (ERA5)
# (O Open-Meteo tem dados históricos desde 1940; para 1939, usamos 1940-2026)
dfs = []
for nome, (lat, lon) in estacoes.items():
    print(f"Baixando {nome}...")
    url = f"https://archive-api.open-meteo.com/v1/archive?latitude={lat}&longitude={lon}&start_date=1940-01-01&end_date=2026-10-30&daily=precipitation_sum&timezone=America%2FSao_Paulo"
    r = requests.get(url)
    data = r.json()
    df = pd.DataFrame({
        "data": pd.to_datetime(data["daily"]["time"]),
        "chuva_mm": data["daily"]["precipitation_sum"],
        "estacao": nome
    })
    dfs.append(df)
    time.sleep(1)  # Evitar rate limit

# Concatenar e pivotar
df_chuva = pd.concat(dfs)
df_chuva = df_chuva.pivot(index="data", columns="estacao", values="chuva_mm")
df_chuva["chuva_montante_24h"] = df_chuva.sum(axis=1)
df_chuva["chuva_montante_72h"] = df_chuva["chuva_montante_24h"].rolling(3).sum()
df_chuva["chuva_montante_7d"] = df_chuva["chuva_montante_24h"].rolling(7).sum()

df_chuva.to_csv(BASE / "data" / "chuva_montante_historica.csv")
print(f"✅ Chuva a montante histórica salva em: data/chuva_montante_historica.csv")
print(f"   Período: {df_chuva.index.min()} a {df_chuva.index.max()}")
print(f"   Linhas: {len(df_chuva)}")
