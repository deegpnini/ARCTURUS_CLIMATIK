import ee
import json
import os

ee.Initialize(project='chrome-setting-477722-d9')
print("✅ GEE inicializado")

# Bounding box
bbox = ee.Geometry.Rectangle([-49.3, -28.5, -48.9, -28.2])

# MDE e máscara (mesmos parâmetros do script anterior)
srtm = ee.Image('USGS/SRTMGL1_003')
ALTITUDE_INUNDACAO = 27.46
mascara = srtm.lte(ALTITUDE_INUNDACAO)

# Converter a máscara (raster) em vetor (polígono) para exportar como KML
# Reduzir a resolução para não gerar um arquivo gigante
mancha_vetor = mascara.reduceToVectors(
    geometry=bbox,
    scale=100,  # 100m (mais grosseiro para o KML não ficar gigante)
    geometryType='polygon',
    maxPixels=1e9
)

# Pegar a primeira feição (o polígono da mancha)
feicoes = mancha_vetor.getInfo()['features']
print(f"Polígonos gerados: {len(feicoes)}")

# Salvar como GeoJSON (que o Google Earth Pro lê)
caminho_saida = "mancha_inundacao.geojson"
with open(caminho_saida, "w") as f:
    json.dump(feicoes[0], f)  # Salvando só o primeiro para teste

print(f"✅ Salvo: {caminho_saida}")
print("Para abrir no Google Earth: Arraste o arquivo para a janela do programa.")
