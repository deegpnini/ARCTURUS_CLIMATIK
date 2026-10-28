import argparse
import json
import math
import os
import tempfile
from pathlib import Path

import ee
import geopandas as gpd
import rasterio
import requests
from rasterio.features import shapes
from shapely.geometry import MultiPolygon, Polygon, shape
from shapely.strtree import STRtree


ROOT = Path(__file__).resolve().parent
AOI_BOUNDS = (-49.2, -28.8, -48.6, -28.2)
COLLECTION_ID = "GOOGLE/Research/open-buildings/v3/polygons"
RASTER_PATH = ROOT / "mapa_inundacao_tubarao_2019_binario.tif"
GPKG_PATH = ROOT / "cache" / "buildings_open_buildings.gpkg"
RESULT_PATH = ROOT / "resultados" / "dano_inundacao_tubarao_2019_edificacoes.json"


def download_tile(bounds, output_path, is_first_write, depth=0):
    min_lon, min_lat, max_lon, max_lat = bounds
    tile = ee.Geometry.Rectangle([min_lon, min_lat, max_lon, max_lat])
    collection = ee.FeatureCollection(COLLECTION_ID).filterBounds(tile)
    url = collection.getDownloadURL(
        filetype="geojson",
        filename="buildings_open_buildings",
    )
    response = requests.get(url, timeout=300)
    if not response.ok:
        if response.status_code >= 500 and depth < 5:
            mid_lon = (min_lon + max_lon) / 2
            mid_lat = (min_lat + max_lat) / 2
            subtiles = (
                (min_lon, min_lat, mid_lon, mid_lat),
                (mid_lon, min_lat, max_lon, mid_lat),
                (min_lon, mid_lat, mid_lon, max_lat),
                (mid_lon, mid_lat, max_lon, max_lat),
            )
            for subtile in subtiles:
                is_first_write = download_tile(
                    subtile, output_path, is_first_write, depth + 1
                )
            return is_first_write
        raise RuntimeError(
            "Falha ao baixar tile do Earth Engine "
            f"(HTTP {response.status_code}): {response.text[:2000]}"
        )
    if not response.content:
        raise RuntimeError("O download de um tile do Earth Engine veio vazio.")

    with tempfile.NamedTemporaryFile(suffix=".geojson", delete=False) as temp_file:
        temp_file.write(response.content)
        temp_path = Path(temp_file.name)
    try:
        tile_buildings = gpd.read_file(temp_path)
    finally:
        temp_path.unlink(missing_ok=True)

    if tile_buildings.empty:
        return is_first_write
    if tile_buildings.crs is None:
        tile_buildings = tile_buildings.set_crs("EPSG:4326")
    else:
        tile_buildings = tile_buildings.to_crs("EPSG:4326")

    tile_buildings.geometry = tile_buildings.geometry.map(
        lambda geometry: MultiPolygon([geometry])
        if isinstance(geometry, Polygon)
        else geometry
    )
    representatives = (
        tile_buildings.to_crs("EPSG:32722")
        .geometry.representative_point()
        .to_crs("EPSG:4326")
    )
    in_tile = (
        (representatives.x >= min_lon)
        & (representatives.y >= min_lat)
        & (representatives.x < max_lon)
        & (representatives.y < max_lat)
    )
    selected = tile_buildings.loc[in_tile]
    if selected.empty:
        return is_first_write
    selected.to_file(
        output_path,
        layer="buildings",
        driver="GPKG",
        mode="w" if is_first_write else "a",
        index=False,
    )
    print(f"Salvas {len(selected)} edificações do tile {bounds}.")
    return False


def download_buildings():
    ee.Initialize(project="chrome-setting-477722-d9")
    aoi = ee.Geometry.Rectangle(list(AOI_BOUNDS))
    buildings = ee.FeatureCollection(COLLECTION_ID).filterBounds(aoi)
    count = buildings.size().getInfo()
    if not count:
        raise RuntimeError("Open Buildings não retornou edificações para o AOI.")
    print(f"Earth Engine encontrou {count} edificações no AOI.")

    GPKG_PATH.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        suffix=".gpkg", prefix="buildings_open_buildings_", dir=GPKG_PATH.parent
    )
    os.close(descriptor)
    temp_gpkg = Path(temp_name)
    try:
        first_write = True
        tile_size = 0.1
        min_lon, min_lat, max_lon, max_lat = AOI_BOUNDS
        lon_steps = math.ceil((max_lon - min_lon) / tile_size)
        lat_steps = math.ceil((max_lat - min_lat) / tile_size)
        for lon_step in range(lon_steps):
            tile_min_lon = min_lon + lon_step * tile_size
            tile_max_lon = min(tile_min_lon + tile_size, max_lon)
            for lat_step in range(lat_steps):
                tile_min_lat = min_lat + lat_step * tile_size
                tile_max_lat = min(tile_min_lat + tile_size, max_lat)
                first_write = download_tile(
                    (tile_min_lon, tile_min_lat, tile_max_lon, tile_max_lat),
                    temp_gpkg,
                    first_write,
                )
        if first_write:
            raise RuntimeError("Nenhum footprint foi salvo no GeoPackage.")
        if GPKG_PATH.exists():
            GPKG_PATH.unlink()
        temp_gpkg.replace(GPKG_PATH)
    finally:
        temp_gpkg.unlink(missing_ok=True)
    return gpd.read_file(GPKG_PATH, layer="buildings", use_arrow=True)


def flood_geometries_in_crs(target_crs):
    with rasterio.open(RASTER_PATH) as raster:
        band = raster.read(1)
        if raster.crs is None:
            raise ValueError(f"O raster não declara CRS: {RASTER_PATH}")
        geometries = [
            shape(geometry)
            for geometry, value in shapes(
                band,
                mask=band > 0,
                transform=raster.transform,
            )
            if value > 0
        ]
        if not geometries:
            raise RuntimeError("A máscara de inundação não contém pixels positivos.")
        flood = gpd.GeoSeries(geometries, crs=raster.crs)
    return flood.to_crs(target_crs).array


def main():
    parser = argparse.ArgumentParser(
        description="Baixa footprints do Open Buildings e cruza com a máscara."
    )
    parser.add_argument(
        "--reprocess-cache",
        action="store_true",
        help="Reusa o GeoPackage existente sem baixar novamente do Earth Engine.",
    )
    args = parser.parse_args()

    if not RASTER_PATH.is_file():
        raise FileNotFoundError(f"Máscara de inundação não encontrada: {RASTER_PATH}")

    if args.reprocess_cache:
        if not GPKG_PATH.is_file():
            raise FileNotFoundError(f"GeoPackage não encontrado: {GPKG_PATH}")
        buildings = gpd.read_file(
            GPKG_PATH,
            layer="buildings",
            use_arrow=True,
        )
    else:
        buildings = download_buildings()

    flood_geometries = flood_geometries_in_crs(buildings.crs)
    building_geometries = buildings.geometry.to_numpy()
    tree = STRtree(building_geometries)
    affected_indices = set()
    for flood_geometry in flood_geometries:
        affected_indices.update(
            tree.query(flood_geometry, predicate="intersects").tolist()
        )
    total_count = len(buildings)
    affected_count = len(affected_indices)

    result = {
        "evento": "Maio/2019",
        "fonte_edificacoes": COLLECTION_ID,
        "bbox_lonlat": list(AOI_BOUNDS),
        "raster_inundacao": RASTER_PATH.name,
        "edificacoes_totais": total_count,
        "edificacoes_afetadas": affected_count,
        "percentual_edificacoes_afetadas": round(
            affected_count / total_count * 100 if total_count else 0,
            2,
        ),
        "metodo": "Interseção dos polígonos com pixels positivos da máscara binária.",
        "arquivo_geopackage": str(GPKG_PATH.relative_to(ROOT)),
    }

    RESULT_PATH.parent.mkdir(parents=True, exist_ok=True)
    RESULT_PATH.write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(result, indent=2, ensure_ascii=False))
    print(f"GeoPackage salvo em: {GPKG_PATH}")
    print(f"Resultado salvo em: {RESULT_PATH}")


if __name__ == "__main__":
    main()
