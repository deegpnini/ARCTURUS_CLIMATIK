import pandas as pd
import geopandas as gpd
import requests
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a mancha de inundação de 2019 (GeoJSON)
mancha_path = BASE / "cache" / "mancha_2019.geojson"
if not mancha_path.exists():
    mancha_shp = BASE / "cache" / "mancha_2019.shp"
    if mancha_shp.exists():
        mancha = gpd.read_file(mancha_shp)
        mancha.to_file(mancha_path, driver="GeoJSON")
    else:
        print("❌ Mancha não encontrada.")
        exit(1)

mancha = gpd.read_file(mancha_path)
mancha = mancha.to_crs("EPSG:4326")
print(f"✅ Mancha carregada: {len(mancha)} polígonos")

# 2. Buscar escolas/UBS via Nominatim
def buscar_nominatim(query, nome):
    url = "https://nominatim.openstreetmap.org/search"
    params = {"q": query, "format": "json", "limit": 100}
    headers = {"User-Agent": "ARCTURUS-CLIMATIK/1.0 (pesquisa hidrologica)"}
    try:
        r = requests.get(url, params=params, headers=headers, timeout=30)
        data = r.json()
        registros = []
        for item in data:
            lat = float(item.get("lat", 0))
            lon = float(item.get("lon", 0))
            if lat and lon:
                registros.append({"nome": item.get("display_name", ""), "lat": lat, "lon": lon})
        df = pd.DataFrame(registros)
        print(f"✅ {nome}: {len(df)} encontrados")
        return df
    except Exception as e:
        print(f"❌ {nome}: erro {e}")
        return pd.DataFrame()

escolas = buscar_nominatim("escola, Tubarão, SC", "Escolas")
ubs = buscar_nominatim("UBS, Tubarão, SC", "UBS")
hospitais = buscar_nominatim("hospital, Tubarão, SC", "Hospitais")

# 3. Cruzar com a mancha de 2019 (usando sjoin, sem unary_union)
def cruzar_com_mancha(df, nome):
    if len(df) == 0:
        return 0
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
    # Spatial join: pontos que estão dentro da mancha
    afetados = gpd.sjoin(gdf, mancha, how="inner", predicate="within")
    # Remover duplicatas (um ponto pode estar em vários polígonos)
    afetados = afetados.drop_duplicates(subset=["lat", "lon"])
    print(f"✅ {nome} afetados: {len(afetados)} de {len(df)}")
    return len(afetados)

escolas_afetadas = cruzar_com_mancha(escolas, "Escolas")
ubs_afetadas = cruzar_com_mancha(ubs, "UBS")
hospitais_afetados = cruzar_com_mancha(hospitais, "Hospitais")

# 4. Estimar a população afetada
edificacoes_afetadas = 1290
populacao_estimada = edificacoes_afetadas * 3

# 5. Salvar o relatório
relatorio = {
    "evento": "Maio/2019",
    "edificacoes_afetadas": edificacoes_afetadas,
    "escolas_afetadas": escolas_afetadas,
    "ubs_afetadas": ubs_afetadas,
    "hospitais_afetados": hospitais_afetados,
    "populacao_estimada": populacao_estimada,
}
with open(BASE / "resultados" / "atlas_impacto_2019.json", "w") as f:
    json.dump(relatorio, f, indent=2)

print("\n=== A.C. ATLAS (IMPACTO 2019) ===")
print(json.dumps(relatorio, indent=2))
print(f"\n✅ Relatório salvo em: resultados/atlas_impacto_2019.json")
