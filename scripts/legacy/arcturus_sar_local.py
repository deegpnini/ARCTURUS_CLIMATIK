#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — PROCESSADOR SAR LOCAL
# Lê o GeoTIFF exportado do GEE e gera GeoJSON
# ============================================================

import os
import json
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "ARCTURUS_CLIMATIK"
SAR_DIR = BASE / "dados" / "sar"
CACHE_FILE = BASE / "cache" / "arcturus_sar.json"

SAR_DIR.mkdir(parents=True, exist_ok=True)
CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)

def listar_tiffs():
    """Lista todos os GeoTIFFs baixados do GEE."""
    if not SAR_DIR.exists():
        return []
    return list(SAR_DIR.glob("*.tif"))

def processar_tiff(arquivo):
    """Processa um GeoTIFF de flood e extrai métricas."""
    try:
        import rasterio
        import numpy as np
        
        with rasterio.open(arquivo) as src:
            band = src.read(1)
            mask = band > 0
            
            # Contar pixels inundados
            pixels = int(np.sum(mask))
            
            # Calcular área (resolução 10m = 100 m² por pixel)
            area_km2 = (pixels * 100) / 1_000_000
            
            # Bounds da área inundada
            bounds = src.bounds
            
            return {
                "arquivo": arquivo.name,
                "pixels": pixels,
                "area_km2": round(area_km2, 2),
                "bounds": {
                    "min_lon": bounds.left,
                    "min_lat": bounds.bottom,
                    "max_lon": bounds.right,
                    "max_lat": bounds.top,
                },
                "timestamp": datetime.fromtimestamp(arquivo.stat().st_mtime).isoformat(),
            }
    except ImportError:
        print("⚠️ rasterio não instalado. Execute: pip install rasterio")
        return None
    except Exception as e:
        print(f"❌ Erro: {e}")
        return None

def main():
    print("=" * 60)
    print("🛰️ ARCTURUS — PROCESSADOR SAR LOCAL")
    print("=" * 60)
    
    tiffs = listar_tiffs()
    if not tiffs:
        print(f"⚠️ Nenhum GeoTIFF em {SAR_DIR}")
        print("   Baixe o arquivo do Google Drive e salve aqui.")
        return
    
    print(f"📁 {len(tiffs)} arquivos encontrados")
    print()
    
    resultados = []
    for tiff in tiffs:
        print(f"🛰️ Processando: {tiff.name}")
        resultado = processar_tiff(tiff)
        if resultado:
            resultados.append(resultado)
            print(f"   ✅ Área: {resultado['area_km2']} km²")
        print()
    
    # Salvar cache
    cache = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_arquivos": len(resultados),
        "resultados": resultados,
    }
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    print(f"✅ Cache: {CACHE_FILE}")

if __name__ == "__main__":
    main()
