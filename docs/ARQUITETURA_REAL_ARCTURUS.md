# ARQUITETURA REAL DO ARCTURUS CLIMATIK

## A.C. Monitor

Fontes:
- ANA
- ERAB
- Defesa Civil

Objetivo:
- Monitoramento hidrológico operacional
- Níveis
- Vazões
- Alertas

---

## A.C. Geo

Dados identificados:
- data/pontos_alagamento_tubarao.json
- data/trajeto_rio_tubarao.json

Capacidades:
- Bairros críticos
- Camada territorial
- Trajeto da Bacia do Rio Tubarão

---

## A.C. Sentinel

Fontes:
- Sentinel-1
- Google Earth Engine

Arquivos:
- mapa_inundacao_tubarao_2019.tif
- mapa_inundacao_tubarao_2019_binario.tif

Produtos:
- Mancha de inundação
- Raster georreferenciado
- Vetorização

---

## A.C. Atlas

Arquivos:
- cache/mancha_2019.geojson
- resultados/mapa_atlas.png
- resultados/mapa_atlas.html

Capacidades:
- Escolas
- UBS
- Hospitais
- Infraestrutura crítica

---

## Impacto Territorial

Arquivos:
- resultados/dano_inundacao_tubarao_2019_edificacoes.json

Resultados identificados:
- 360920 edificações analisadas
- 1290 edificações afetadas

Fonte:
- Google Open Buildings

---

## Sensoriamento Remoto

Arquivos:
- src/relatorios/mapa_recorrencia_sentinel1.py
- scripts/legacy/arcturus_sar.py
- scripts/legacy/arcturus_sar_local.py

Capacidades identificadas:
- Detecção de água
- Processamento SAR
- Exportação GeoTIFF
- Avaliação espacial

---

## Descobertas da Fase 1

- Pipeline Sentinel identificado
- Atlas identificado
- Mancha 2019 identificada
- GeoJSON identificado
- Shapefile identificado
- Open Buildings identificado
- Arquitetura Monitor / Geo / Sentinel / Atlas identificada

