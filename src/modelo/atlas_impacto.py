import pandas as pd
import geopandas as gpd
import requests
import json
import time
from pathlib import Path
from shapely.geometry import box

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
print(f"✅ Mancha carregada: {len(mancha)} polígonos")

# 2. Baixar escolas do OSM (via Overpass, com retry)
def baixar_osm(tag, valor, nome, tentativas=3, espera=10):
    bbox = (-49.2, -28.8, -48.6, -28.2)
    query = f"""
    [out:json];
    (
      node["{tag}"="{valor}"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
      way["{tag}"="{valor}"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
      relation["{tag}"="{valor}"]({bbox[1]},{bbox[0]},{bbox[3]},{bbox[2]});
    );
    out center;
    """
    url = "https://overpass-api.de/api/interpreter"
    for i in range(tentativas):
        try:
            r = requests.post(url, data={"data": query}, timeout=60)
            if r.status_code == 200 and r.text.strip().startswith("{"):
                data = r.json()
                elementos = data.get("elements", [])
                registros = []
                for el in elementos:
                    lat = el.get("lat") or el.get("center", {}).get("lat")
                    lon = el.get("lon") or el.get("center", {}).get("lon")
                    nome_el = el.get("tags", {}).get("name", "")
                    if lat and lon:
                        registros.append({"nome": nome_el, "lat": lat, "lon": lon})
                df = pd.DataFrame(registros)
                print(f"✅ {nome}: {len(df)} encontrados")
                return df
            else:
                print(f"⚠️ Tentativa {i+1}/{tentativas} falhou (status {r.status_code}). Esperando {espera}s...")
                time.sleep(espera)
        except Exception as e:
            print(f"⚠️ Tentativa {i+1}/{tentativas} falhou: {e}. Esperando {espera}s...")
            time.sleep(espera)
    print(f"❌ {nome}: todas as tentativas falharam.")
    return pd.DataFrame()

escolas = baixar_osm("amenity", "school", "Escolas")
ubs = baixar_osm("amenity", "clinic", "UBS/Clínicas")
hospitais = baixar_osm("amenity", "hospital", "Hospitais")

# 3. Cruzar com a mancha de 2019
def cruzar_com_mancha(df, nome):
    if len(df) == 0:
        return 0
    gdf = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs="EPSG:4326")
    mancha_4326 = mancha.to_crs("EPSG:4326")
    mancha_unida = mancha_4326.unary_union
    afetados = gdf[gdf.intersects(mancha_unida)]
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
