#!/usr/bin/env python3
# ============================================================
# ARCTURUS — BAIXAR COORDENADAS DOS MUNICÍPIOS DE SC
# ============================================================

import json
import time
import urllib.request
import urllib.parse
from pathlib import Path

BASE = Path.home() / "ARCTURUS_CLIMATIK"
DIR_FONTES = BASE / "fontes"

# Nominatim (OpenStreetMap) - gratuito, precisa user-agent
URL_NOMINATIM = "https://nominatim.openstreetmap.org/search"

def buscar_coordenadas(nome, uf="SC"):
    params = {
        "q": f"{nome}, {uf}, Brasil",
        "format": "json",
        "limit": 1,
    }
    url = URL_NOMINATIM + "?" + urllib.parse.urlencode(params)
    headers = {
        "User-Agent": "ARCTURUS-CLIMATIK/1.0 (contato: nexus-oikos)"
    }
    
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            dados = json.loads(r.read().decode("utf-8"))
            if dados:
                return float(dados[0]["lat"]), float(dados[0]["lon"])
    except Exception as e:
        print(f"  ⚠️  {nome}: {e}")
    return None, None

def main():
    entrada = DIR_FONTES / "municipios_sc_ibge.json"
    with open(entrada, "r", encoding="utf-8") as f:
        municipios = json.load(f)
    
    print(f"📡 Buscando coordenadas de {len(municipios)} municípios...")
    print("   (isso pode levar 15-25 minutos)")
    print()
    
    # Cache: se já tem, pula
    cache_file = DIR_FONTES / "municipios_sc_coords.json"
    if cache_file.exists():
        with open(cache_file, "r", encoding="utf-8") as f:
            cache = json.load(f)
        print(f"✅ Cache encontrado: {len(cache)} municípios já têm coords")
        ja_tem = {m["codigo_ibge"] for m in cache}
    else:
        cache = []
        ja_tem = set()
    
    for i, m in enumerate(municipios, 1):
        if m["codigo_ibge"] in ja_tem:
            continue
        
        lat, lon = buscar_coordenadas(m["nome"])
        if lat and lon:
            cache.append({
                "codigo_ibge": m["codigo_ibge"],
                "nome": m["nome"],
                "lat": lat,
                "lon": lon,
            })
            print(f"  [{i:>3}/{len(municipios)}] {m['nome']:<35} ({lat:.4f}, {lon:.4f})")
        else:
            print(f"  [{i:>3}/{len(municipios)}] {m['nome']:<35} ❌ sem coords")
        
        # Salvar incremental (a cada 10)
        if i % 10 == 0:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
        
        # Rate limit do Nominatim: 1 req/seg
        time.sleep(1.1)
    
    # Salvar final
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    print()
    print(f"💾 Salvo: {cache_file}")
    print(f"✅ Total com coordenadas: {len(cache)}/{len(municipios)}")

if __name__ == "__main__":
    main()
