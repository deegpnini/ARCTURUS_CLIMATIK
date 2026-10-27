import ee
from pathlib import Path
from datetime import datetime, timedelta

ee.Initialize(project='chrome-setting-477722-d9')

# Área de interesse: Baixo Rio Tubarão (conforme estudo do ISPRS)
# O estudo cobre Tubarão, Laguna, Jaguaruna, Capivari de Baixo, Sangão, Treze de Maio
bbox = ee.Geometry.Rectangle([-49.2, -28.8, -48.6, -28.2])

# Evento do estudo: 24-25 de maio de 2019 (260 mm de chuva)
# Imagem pós-evento: 28-29 de maio de 2019 (3 dias depois)
eventos = [
    {"nome": "2019 (estudo ISPRS)", "data": "2019-05-28"},
]

def detectar_agua(imagem):
    vv = imagem.select('VV')
    return vv.lt(-18)

mapa_agua = None
for ev in eventos:
    data = datetime.strptime(ev["data"], "%Y-%m-%d")
    inicio = (data - timedelta(days=2)).strftime("%Y-%m-%d")
    fim = (data + timedelta(days=2)).strftime("%Y-%m-%d")
    
    print(f"\n🔍 Buscando imagem para {ev['nome']} ({inicio} a {fim})...")
    
    # Tenta DESCENDING primeiro (melhor cobertura para o Sul do Brasil)
    colecao = (ee.ImageCollection('COPERNICUS/S1_GRD')
                .filterDate(inicio, fim)
                .filterBounds(bbox)
                .filter(ee.Filter.eq('instrumentMode', 'IW'))
                .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
                .filter(ee.Filter.eq('orbitProperties_pass', 'DESCENDING')))
    
    size = colecao.size().getInfo()
    if size == 0:
        print(f"⚠️ Nenhuma DESCENDING. Tentando ASCENDING...")
        colecao = (ee.ImageCollection('COPERNICUS/S1_GRD')
                    .filterDate(inicio, fim)
                    .filterBounds(bbox)
                    .filter(ee.Filter.eq('instrumentMode', 'IW'))
                    .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
                    .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING')))
        size = colecao.size().getInfo()
    
    if size == 0:
        print(f"⚠️ Nenhuma imagem encontrada para {ev['nome']}. Pulando.")
        continue
    
    print(f"✅ {size} imagem(ns) encontrada(s) para {ev['nome']}.")
    imagem = colecao.first()
    agua = detectar_agua(imagem)
    mapa_agua = agua

if mapa_agua is not None:
    # Exporta a MÁSCARA BINÁRIA (0 = não alagado, 1 = alagado)
    # Converte para uint8 (0 e 1)
    mapa_binario = mapa_agua.uint8()
    task = ee.batch.Export.image.toDrive(
        image=mapa_binario,
        description='mapa_inundacao_tubarao_2019_binario',
        folder='ARCTURUS',
        scale=30,
        region=bbox,
        fileFormat='GeoTIFF'
    )
    task.start()
    print(f"\n✅ Exportação iniciada. Task ID: {task.id}")
    print(f"   O arquivo estará no Google Drive (pasta ARCTURUS).")
else:
    print("\n❌ Nenhuma imagem encontrada. Verifique a data.")

print("\n✅ Script concluído.")
