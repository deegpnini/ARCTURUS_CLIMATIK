import time, requests, pandas as pd
from pathlib import Path

PONTOS = {
    "lauro_muller": (-28.393, -49.396), "orleans": (-28.360, -49.295),
    "grao_para": (-28.181, -49.225), "braco_norte": (-28.275, -49.168),
    "sao_ludgero": (-28.316, -49.183), "rio_fortuna": (-28.122, -49.114),
    "pedras_grandes": (-28.434, -49.188), "pouso": (-28.4206, -49.1064),
}
URL = "https://archive-api.open-meteo.com/v1/archive"
out = {}
for nome, (lat, lon) in PONTOS.items():
    for tent in range(4):
        r = requests.get(URL, params=dict(latitude=lat, longitude=lon, start_date="2023-11-25",
                         end_date="2026-09-22", hourly="precipitation",
                         timezone="America/Sao_Paulo"), timeout=60)
        if r.status_code == 200:
            break
        time.sleep(5 * (tent + 1))
    r.raise_for_status()
    h = r.json()["hourly"]
    out[nome] = pd.Series(h["precipitation"], index=pd.to_datetime(h["time"]))
    print(nome, len(out[nome]), "NaN:", int(out[nome].isna().sum()), "soma mm:", round(out[nome].sum()))
    time.sleep(2)
df = pd.DataFrame(out); df.index.name = "timestamp"
df.to_csv(Path("data") / "chuva_bacia_openmeteo.csv")
print(df.index.min(), df.index.max(), df.shape)
