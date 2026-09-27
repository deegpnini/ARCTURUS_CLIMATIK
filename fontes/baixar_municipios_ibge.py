#!/usr/bin/env python3
# ============================================================
# ARCTURUS — BAIXAR MUNICÍPIOS DE SC (IBGE) - v2
# ============================================================

import json
import gzip
import urllib.request
from pathlib import Path

BASE = Path.home() / "ARCTURUS_CLIMATIK"
DIR_FONTES = BASE / "fontes"
DIR_FONTES.mkdir(parents=True, exist_ok=True)

URL_IBGE = "https://servicodados.ibge.gov.br/api/v1/localidades/estados/SC/municipios"

def baixar_json(url):
    """Baixa JSON tratando gzip explicitamente."""
    headers = {
        "User-Agent": "ARCTURUS-CLIMATIK/1.0",
        "Accept": "application/json",
        "Accept-Encoding": "gzip",
    }
    
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        conteudo = resp.read()
        
        # Tentar descomprimir se for gzip
        if conteudo[:2] == b"\x1f\x8b":
            print("  (resposta comprimida em gzip, descomprimindo...)")
            conteudo = gzip.decompress(conteudo)
        
        return json.loads(conteudo.decode("utf-8"))

def main():
    print("📡 Baixando municípios de SC do IBGE...")
    
    try:
        dados = baixar_json(URL_IBGE)
    except Exception as e:
        print(f"❌ Erro ao baixar: {e}")
        return
    
    municipios = []
    for m in dados:
        municipios.append({
            "codigo_ibge": m["id"],
            "nome": m["nome"],
        })
    
    print(f"✅ {len(municipios)} municípios baixados")
    
    saida = DIR_FONTES / "municipios_sc_ibge.json"
    with open(saida, "w", encoding="utf-8") as f:
        json.dump(municipios, f, ensure_ascii=False, indent=2)
    
    print(f"💾 Salvo: {saida}")
    print()
    print("📋 Amostra (5 primeiros):")
    for m in municipios[:5]:
        print(f"  {m['codigo_ibge']:>7} - {m['nome']}")
    print(f"  ... (total: {len(municipios)})")

if __name__ == "__main__":
    main()
