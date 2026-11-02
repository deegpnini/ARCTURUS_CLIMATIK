import pandas as pd
import geopandas as gpd
import requests
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a mancha de inundação
mancha = gpd.read_file(BASE / "cache" / "mancha_2019.geojson").to_crs("EPSG:4326")

# 2. Buscar escolas/UBS via Nominatim
def buscar_nominatim(query, nome):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 100}
    headers = {"User-Agent": "ARCTURUS-CLIMATIK/1.0"}
    r = requests.get(url, params=params, headers=headers, timeout=30)
    data = r.json()
    registros = []
    for item in data:
        lat = float(item.get("lat", 0))
        lon = float(item.get("lon", 0))
        if lat and lon:
            registros.append({"nome": item.get("display_name", ""), "lat": lat, "lon": lon})
    return pd.DataFrame(registros)

escolas = buscar_nominatim("escola, Tubarão, SC", "Escolas")
ubs = buscar_nominatim("UBS, Tubarão, SC", "UBS")
hospitais = buscar_nominatim("hospital, Tubarão, SC", "Hospitais")

# 3. Plotar a mancha + os pontos (matplotlib)
fig, ax = plt.subplots(figsize=(12, 10))
mancha.plot(ax=ax, color="blue", alpha=0.3, edgecolor="blue", linewidth=0.5)
if len(escolas) > 0:
    ax.scatter(escolas["lon"], escolas["lat"], c="red", s=50, label="Escolas", zorder=5)
if len(ubs) > 0:
    ax.scatter(ubs["lon"], ubs["lat"], c="green", s=50, label="UBS", zorder=5)
if len(hospitais) > 0:
    ax.scatter(hospitais["lon"], hospitais["lat"], c="orange", s=50, label="Hospitais", zorder=5)
ax.set_title("A.C. Atlas — Mancha 2019 + Escolas/UBS/Hospitais")
ax.set_xlabel("Longitude")
ax.set_ylabel("Latitude")
ax.legend()
plt.tight_layout()
plt.savefig(BASE / "resultados" / "mapa_atlas.png", dpi=150)
print(f"✅ Mapa salvo em: resultados/mapa_atlas.png")
