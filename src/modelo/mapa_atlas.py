import pandas as pd
import geopandas as gpd
import requests
import folium
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

# 3. Criar o mapa (Folium)
# Centro do mapa: Tubarão (-28.48, -49.02)
mapa = folium.Map(location=[-28.48, -49.02], zoom_start=12)

# Adicionar a mancha (polígonos)
for _, row in mancha.iterrows():
    folium.GeoJson(row.geometry.__geo_interface__, style_function=lambda x: {"fillColor": "blue", "color": "blue", "weight": 1, "fillOpacity": 0.3}).add_to(mapa)

# Adicionar as escolas (vermelho)
for _, row in escolas.iterrows():
    folium.CircleMarker(location=[row["lat"], row["lon"]], radius=5, color="red", fill=True, popup=row["nome"]).add_to(mapa)

# Adicionar as UBS (verde)
for _, row in ubs.iterrows():
    folium.CircleMarker(location=[row["lat"], row["lon"]], radius=5, color="green", fill=True, popup=row["nome"]).add_to(mapa)

# Adicionar os hospitais (laranja)
for _, row in hospitais.iterrows():
    folium.CircleMarker(location=[row["lat"], row["lon"]], radius=5, color="orange", fill=True, popup=row["nome"]).add_to(mapa)

# Salvar o mapa
mapa.save(BASE / "resultados" / "mapa_atlas.html")
print(f"✅ Mapa salvo em: resultados/mapa_atlas.html")
print(f"   Abra no navegador: file://{BASE}/resultados/mapa_atlas.html")
