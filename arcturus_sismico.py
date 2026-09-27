#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — MÓDULO SÍSMICO
# USGS (eventos em SC)
# ============================================================

import os
import json
import ssl
import urllib.request
from datetime import datetime, timedelta
from pathlib import Path
import certifi

BASE = Path.home() / "ARCTURUS_CLIMATIK"
CACHE_FILE = BASE / "cache" / "arcturus_sismico.json"
LOG_FILE = BASE / "logs" / "sismico.log"

CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def fetch(url, timeout=15):
    ctx = ssl.create_default_context(cafile=certifi.where())
    req = urllib.request.Request(url, headers={
        "User-Agent": "ARCTURUS/1.0",
        "Accept": "application/json"
    })
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception as e:
        log(f"   ⚠️ {str(e)[:80]}")
        return None

def main():
    log("=" * 60)
    log("🌍 ARCTURUS — VARREDURA SÍSMICA")
    log("=" * 60)
    
    # USGS — eventos dos últimos 30 dias em SC
    agora = datetime.now()
    inicio = (agora - timedelta(days=365)).strftime("%Y-%m-%d")
    
    url = (
        f"https://earthquake.usgs.gov/fdsnws/event/1/query?"
        f"format=geojson"
        f"&starttime={inicio}"
        f"&minlatitude=-30&maxlatitude=-25"
        f"&minlongitude=-55&maxlongitude=-48"
        f"&minmagnitude=1.0"
        f"&limit=100"
    )
    
    data = fetch(url)
    if not data:
        log("❌ USGS indisponível")
        return
    
    eventos = []
    for f in data.get("features", []):
        p = f["properties"]
        g = f["geometry"]["coordinates"]
        eventos.append({
            "id": p.get("id"),
            "data": datetime.fromtimestamp(p["time"] / 1000).strftime("%d/%m/%Y %H:%M"),
            "magnitude": p.get("mag"),
            "localizacao": p.get("place"),
            "latitude": g[1],
            "longitude": g[0],
            "profundidade_km": g[2],
        })
    
    cache = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "total_eventos": len(eventos),
        "periodo": f"{inicio} a {agora.strftime('%Y-%m-%d')}",
        "eventos": eventos,
        "status": "🟢 NORMAL" if len(eventos) == 0 else "🟡 ATIVIDADE",
    }
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    log(f"✅ {len(eventos)} eventos nos últimos 12 meses")
    log(f"✅ Cache: {CACHE_FILE}")
    log("=" * 60)
    
    print()
    print(f"📊 EVENTOS SÍSMICOS EM SC (últimos 12 meses):")
    if eventos:
        for e in eventos[:5]:
            print(f"  M{e['magnitude']} | {e['data']} | {e['localizacao']}")
    else:
        print("  ✅ Nenhum evento detectado — região estável")

if __name__ == "__main__":
    main()
