import warnings
import geopandas as gpd
import rasterio
from rasterio.features import shapes
from pathlib import Path
import floodrisk
from floodrisk import compute_flood_damage

warnings.filterwarnings("ignore")

TIF_PATH = "mapa_inundacao_tubarao_2019_binario.tif"
CACHE_DIR = Path("cache")
ROADS_FILE = CACHE_DIR / "roads_tubarao.gpkg"
BUILDINGS_FILE = CACHE_DIR / "buildings_tubarao.gpkg"
FLOOD_POLY_FILE = CACHE_DIR / "mancha_2019_simplificada.gpkg"

# 1. Converter o .tif em polígono e SIMPLIFICAR (reduzir o volume)
if not FLOOD_POLY_FILE.exists():
    print("🗺️ Convertendo o raster em polígono e simplificando...")
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
        # SIMPLIFY: reduz a resolução (tolerance em metros, 10m é suficiente para 30m de pixel)
        gdf_simplificado = gdf.copy()
        gdf_simplificado['geometry'] = gdf_simplificado['geometry'].simplify(tolerance=10, preserve_topology=True)
        # Remove polígonos vazios (que sumiram com a simplificação)
        gdf_simplificado = gdf_simplificado[~gdf_simplificado.is_empty]
        print(f"   Polígonos após simplificação: {len(gdf_simplificado)}")
        gdf_simplificado.to_file(FLOOD_POLY_FILE, driver="GPKG")
        print(f"✅ Mancha simplificada salva em: {FLOOD_POLY_FILE}")
else:
    print(f"✅ Usando cache da mancha simplificada: {FLOOD_POLY_FILE}")

# 2. Carregar ruas e prédios do cache
print("📂 Carregando ruas e prédios do cache...")
roads = gpd.read_file(ROADS_FILE)
buildings = gpd.read_file(BUILDINGS_FILE)

# 3. Filtrar estradas prioritárias
tipos = ['motorway', 'trunk', 'primary', 'secondary', 'tertiary']
if 'highway' in roads.columns:
    roads_prio = roads[roads['highway'].isin(tipos)]
    print(f"   Estradas totais: {len(roads)} | Prioritárias: {len(roads_prio)}")
else:
    roads_prio = roads

# 4. Calcular dano (com a API correta do floodrisk)
print("🌊 Calculando dano...")
try:
    resultado = compute_flood_damage(roads_prio, buildings, str(FLOOD_POLY_FILE))
    print("\n=== RESULTADO DO DANO ===")
    for key, value in resultado.items():
        print(f"{key}: {value}")
    
    import json
    with open("resultados/dano_inundacao_tubarao_2019.json", "w") as f:
        json.dump(resultado, f, indent=2, default=str)
    print("\n✅ Resultado salvo em: resultados/dano_inundacao_tubarao_2019.json")
except Exception as e:
    print(f"❌ Erro no cálculo: {e}")
    import traceback
    traceback.print_exc()
