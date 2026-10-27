import warnings
import geopandas as gpd
import rasterio
from rasterio.features import shapes
from shapely.geometry import shape
from shapely.ops import unary_union
from pathlib import Path

warnings.filterwarnings("ignore")

TIF_PATH = "mapa_inundacao_tubarao_2019_binario.tif"
CACHE_DIR = Path("cache")
ROADS_FILE = CACHE_DIR / "roads_tubarao.gpkg"
BUILDINGS_FILE = CACHE_DIR / "buildings_tubarao.gpkg"

# 1. Converter o .tif em polígonos
print("🗺️ Convertendo o .tif em polígonos...")
with rasterio.open(TIF_PATH) as src:
    banda = src.read(1)
    results = (
        {'properties': {'value': v}, 'geometry': s}
        for i, (s, v) in enumerate(shapes(banda, mask=(banda > 0), transform=src.transform))
    )
    geoms = list(results)
    if len(geoms) == 0:
        print("❌ Nenhum polígono de água encontrado.")
        exit(1)
    gdf = gpd.GeoDataFrame.from_features(geoms, crs=src.crs)
    print(f"   Polígonos originais: {len(gdf)}")

# 2. Fazer o unary_union (com buffer(0) para corrigir geometrias inválidas)
print("🔗 Unindo polígonos (unary_union)...")
gdf['geometry'] = gdf['geometry'].buffer(0)  # Corrige geometrias inválidas
mancha_unida = unary_union(gdf['geometry'])
print(f"   Mancha unida: {mancha_unida.geom_type}")

# 3. Reprojetar a mancha para o CRS das ruas (EPSG:4326)
print("🔄 Reprojetando a mancha para EPSG:4326...")
mancha_gdf = gpd.GeoDataFrame(geometry=[mancha_unida], crs=gdf.crs)
mancha_gdf = mancha_gdf.to_crs(epsg=4326)
mancha_unida = mancha_gdf.geometry[0]
print(f"   Mancha reprojetada: {mancha_unida.geom_type}")

# 3. Carregar ruas e prédios do cache
print("📂 Carregando ruas e prédios do cache...")
roads = gpd.read_file(ROADS_FILE)
buildings = gpd.read_file(BUILDINGS_FILE)

# 4. Filtrar estradas prioritárias
tipos = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']
if 'highway' in roads.columns:
    roads_prio = roads[roads['highway'].isin(tipos)]
    print(f"   Estradas totais: {len(roads)} | Prioritárias: {len(roads_prio)}")
else:
    roads_prio = roads

# 5. Cruzar a mancha com as ruas e prédios (manual)
print("🌊 Calculando dano (manual)...")

# 5.1 Estradas afetadas
roads_afetadas = roads_prio[roads_prio.intersects(mancha_unida)]
print(f"\n=== ESTRADAS ===")
print(f"Estradas prioritárias: {len(roads_prio)}")
print(f"Estradas afetadas: {len(roads_afetadas)}")
if len(roads_afetadas) > 0:
    # Comprimento total (km) das estradas afetadas
    roads_afetadas_km = roads_afetadas.to_crs(epsg=32722).length.sum() / 1000
    print(f"Comprimento afetado: {roads_afetadas_km:.2f} km")

# 5.2 Prédios afetados
buildings_afetados = buildings[buildings.intersects(mancha_unida)]
print(f"\n=== PRÉDIOS ===")
print(f"Prédios totais: {len(buildings)}")
print(f"Prédios afetados: {len(buildings_afetados)}")
if len(buildings) > 0:
    perc = (len(buildings_afetados) / len(buildings)) * 100
    print(f"Percentual afetado: {perc:.2f}%")

# 6. Salvar o resultado em JSON
import json
resultado = {
    "evento": "Maio/2019",
    "estradas_prioritarias": len(roads_prio),
    "estradas_afetadas": len(roads_afetadas),
    "comprimento_afetado_km": round(roads_afetadas_km, 2) if len(roads_afetadas) > 0 else 0,
    "predios_totais": len(buildings),
    "predios_afetados": len(buildings_afetados),
    "percentual_predios_afetados": round((len(buildings_afetados) / len(buildings)) * 100, 2) if len(buildings) > 0 else 0
}
with open("resultados/dano_inundacao_tubarao_2019.json", "w") as f:
    json.dump(resultado, f, indent=2)
print("\n✅ Resultado salvo em: resultados/dano_inundacao_tubarao_2019.json")
