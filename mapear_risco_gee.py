import ee

ee.Initialize(project='chrome-setting-477722-d9')
print("✅ GEE inicializado")

# Coordenadas da régua do Rio do Pouso (do inventário ANA)
LAT_REGUA = -28.4206
LON_REGUA = -49.1064
ALTITUDE_REGUA = 23.0  # metros

# A cota de enchente (446 cm) foi o pico que vimos
COTA_ENCHENTE_M = 4.46
ALTITUDE_INUNDACAO = ALTITUDE_REGUA + COTA_ENCHENTE_M  # 27.46 m

print(f"📍 Régua do Pouso: {LAT_REGUA}, {LON_REGUA}")
print(f"📏 Altitude da régua: {ALTITUDE_REGUA} m")
print(f"🌊 Altitude de inundação: {ALTITUDE_INUNDACAO:.2f} m")

# Bacia do Tubarão (bounding box da região)
bbox = ee.Geometry.Rectangle([-49.3, -28.5, -48.9, -28.2])

# Carregar MDE
srtm = ee.Image('USGS/SRTMGL1_003')

# Máscara de risco: onde a altitude é menor que a altitude de inundação
mascara_risco = srtm.lte(ALTITUDE_INUNDACAO)

# Calcular área de risco
area_risco = mascara_risco.multiply(ee.Image.pixelArea()).divide(1e6).reduceRegion(
    reducer=ee.Reducer.sum(),
    geometry=bbox,
    scale=30,
    maxPixels=1e9
)

valor_area = area_risco.getInfo().get('elevation')
print(f"\n🌊 Área inundável (abaixo de {ALTITUDE_INUNDACAO:.1f}m):")
print(f"   {valor_area:.2f} km²")
