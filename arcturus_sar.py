#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — MÓDULO SENTINEL-1 SAR
# Detecção de inundações via Google Earth Engine
# ============================================================

import os
import json
import ee
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path.home() / "ARCTURUS_CLIMATIK"
CACHE_FILE = BASE / "cache" / "arcturus_sar.json"
LOG_FILE = BASE / "logs" / "sar.log"

CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

# ============================================================
# INICIALIZAR GEE
# ============================================================
def inicializar_gee():
    try:
        ee.Initialize(project="chrome-setting-477722-d9")
        log("✅ GEE inicializado")
        return True
    except Exception as e:
        log(f"❌ Erro GEE: {e}")
        log("   Execute: earthengine authenticate")
        return False

# ============================================================
# ROIs — Bacias monitoradas
# ============================================================
ROIS = {
    "Blumenau": {
        "bbox": [-49.15, -26.95, -48.95, -26.85],
        "estacao_ana": "83800002",
        "cota_alerta": 8.0,
    },
    "Gaspar": {
        "bbox": [-49.05, -26.98, -48.85, -26.88],
        "estacao_ana": "83800005",
        "cota_alerta": 10.0,
    },
    "Rio do Sul": {
        "bbox": [-49.70, -27.30, -49.55, -27.15],
        "estacao_ana": "83500000",
        "cota_alerta": 8.0,
    },
    "Itajaí": {
        "bbox": [-48.75, -26.95, -48.55, -26.85],
        "estacao_ana": "83810000",
        "cota_alerta": 5.0,
    },
}

# ============================================================
# DETECÇÃO DE INUNDAÇÃO (workflow Filipponi/ESA)
# ============================================================
def detectar_inundacao(nome_rio, dias_pre=10, dias_pos=10):
    """Detecta inundação usando Sentinel-1 GRD."""
    
    log(f"🛰️ Processando {nome_rio}...")
    roi_info = ROIS.get(nome_rio)
    if not roi_info:
        log(f"❌ ROI não encontrado: {nome_rio}")
        return None
    
    roi = ee.Geometry.Rectangle(roi_info["bbox"])
    
    # Sentinel-1 GRD — IW, ASCENDING, VV+VH
    s1 = (ee.ImageCollection('COPERNICUS/S1_GRD')
          .filterBounds(roi)
          .filter(ee.Filter.eq('instrumentMode', 'IW'))
          .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VV'))
          .filter(ee.Filter.listContains('transmitterReceiverPolarisation', 'VH'))
          .filter(ee.Filter.eq('orbitProperties_pass', 'ASCENDING')))
    
    # Período de análise
    hoje = datetime.now()
    pre_inicio = (hoje - timedelta(days=dias_pre + 30)).strftime("%Y-%m-%d")
    pre_fim = (hoje - timedelta(days=dias_pre)).strftime("%Y-%m-%d")
    pos_inicio = (hoje - timedelta(days=dias_pos)).strftime("%Y-%m-%d")
    pos_fim = hoje.strftime("%Y-%m-%d")
    
    log(f"   Pré-evento: {pre_inicio} a {pre_fim}")
    log(f"   Pós-evento: {pos_inicio} a {pos_fim}")
    
    try:
        # Pré-evento (referência de solo seco)
        pre = s1.filterDate(pre_inicio, pre_fim).mosaic().clip(roi)
        
        # Pós-evento (durante/após chuva)
        post = s1.filterDate(pos_inicio, pos_fim).mosaic().clip(roi)
        
        # Detecção por threshold de água (VV < -18 dB)
        agua_post = (post.select('VV').lt(-18)
                     .And(post.select('VH').lt(-22)))
        
        # Change detection (queda > 2.5 dB)
        diff = pre.select('VV').subtract(post.select('VV'))
        flood = diff.gt(2.5).And(agua_post)
        
        # Estatísticas
        stats = flood.selfMask().reduceRegion(
            reducer=ee.Reducer.count(),
            geometry=roi,
            scale=10,
            maxPixels=1e9
        )
        
        pixels_inundados = stats.getInfo().get('VV', 0)
        area_km2 = (pixels_inundados * 100) / 1_000_000  # 100 m² por pixel (10m x 10m)
        
        log(f"   ✅ Área inundada: {area_km2:.2f} km² ({pixels_inundados} pixels)")
        
        # Iniciar export para Google Drive
        task = ee.batch.Export.image.toDrive(
            image=flood.selfMask(),
            description=f'flood_{nome_rio.replace(" ", "_")}',
            folder='ARCTURUS',
            fileNamePrefix=f'flood_{nome_rio}_{datetime.now().strftime("%Y%m%d_%H%M")}',
            region=roi,
            scale=10,
            crs='EPSG:4326',
            fileFormat='GeoTIFF',
            maxPixels=1e9
        )
        task.start()
        log(f"   📤 Export iniciado: {task.id}")
        
        return {
            "roi": nome_rio,
            "area_km2": round(area_km2, 2),
            "pixels": pixels_inundados,
            "periodo_pre": f"{pre_inicio} a {pre_fim}",
            "periodo_pos": f"{pos_inicio} a {pos_fim}",
            "estacao_ana": roi_info["estacao_ana"],
            "cota_alerta": roi_info["cota_alerta"],
            "task_id": task.id,
            "status": "✅ EXPORTANDO" if area_km2 > 0 else "🟢 SEM INUNDAÇÃO",
        }
    
    except Exception as e:
        log(f"   ❌ Erro: {e}")
        return None

# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 60)
    log("🛰️ ARCTURUS — MÓDULO SENTINEL-1 SAR")
    log("=" * 60)
    
    if not inicializar_gee():
        return
    
    resultados = []
    
    for nome_rio in ROIS.keys():
        resultado = detectar_inundacao(nome_rio)
        if resultado:
            resultados.append(resultado)
            log("")
    
    # Salvar cache
    cache = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_rois": len(ROIS),
        "resultados": resultados,
        "fonte": "Sentinel-1 GRD (Copernicus/ESA via GEE)",
        "workflow": "Filipponi/ESA (órbita → calibração → speckle → terrain correction)",
    }
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    log(f"✅ Cache: {CACHE_FILE}")
    log("=" * 60)
    
    print()
    print("📊 RESULTADO:")
    for r in resultados:
        print(f"  {r['status']} {r['roi']}: {r['area_km2']} km²")

if __name__ == "__main__":
    main()
