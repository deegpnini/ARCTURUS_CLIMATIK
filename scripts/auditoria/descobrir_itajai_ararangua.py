#!/usr/bin/env python3
"""
Descobre estacoes em Itajai e Ararangua.
Inclui fluviometricas, pluviometricas, PCDs.
"""
import json, os
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
INV = f"{CACHE}/ana_inventario_sc.json"

# Municipios de cada bacia
MUNICIPIOS = {
    'ITAJAI_ACU': [
        'BLUMENAU', 'INDAIAL', 'RIO DO SUL', 'BRUSQUE', 'GASPAR',
        'NAVEGANTES', 'ILHOTA', 'ITAJAI', 'POMERODE', 'TIMBO',
        'APIUNA', 'ASCURRA', 'BENEDITO NOVO', 'DR PEDRINHO',
        'IBIRAMA', 'JOSE BOITEUX', 'LAURENTINO', 'LONTRAS',
        'PRESIDENTE GETULIO', 'RIO DO OESTE', 'RODEIO',
        'SALETE', 'TAIO', 'TEST0', 'WITMARSUM',
    ],
    'ARARANGUA': [
        'ARARANGUA', 'CRICIUMA', 'SIDEROPOLIS', 'ICARA', 'TIMBE DO SUL',
        'ERMO', 'TURVO', 'FORQUILHINHA', 'MELEIRO', 'MORRO GRANDE',
        'PASSO DE TORRES', 'PRAIA GRANDE', 'SAO JOAO DO SUL',
        'TREVISO', 'MARACAJA', 'NOVA VENEZA', 'LAURO MULLER',
        'URUSSANGA', 'COCAL DO SUL',
    ],
}

def main():
    with open(INV) as f:
        inv = json.load(f)
    items = inv.get('items', [])
    print(f"Inventario: {len(items)} estacoes SC\n")

    for bacia, municipios in MUNICIPIOS.items():
        print(f"\n{'='*90}")
        print(f"BACIA: {bacia}")
        print(f"{'='*90}")

        encontradas = []
        for x in items:
            municipio = str(x.get('Municipio_Nome', '')).upper()
            if any(m in municipio for m in municipios):
                encontradas.append(x)

        print(f"\nTotal de estacoes em municipios da bacia: {len(encontradas)}\n")

        # Agrupa por tipo
        por_tipo = defaultdict(list)
        for x in encontradas:
            tipo = x.get('Tipo_Estacao', 'N/A')
            tele = str(x.get('Tipo_Estacao_Telemetrica', '')).strip()
            oper = str(x.get('Operando', '')).strip()
            por_tipo[tipo].append({
                'codigo': str(x.get('codigoestacao')),
                'nome': x.get('Estacao_Nome'),
                'municipio': x.get('Municipio_Nome'),
                'rio': x.get('Rio_Nome'),
                'tele': tele,
                'oper': oper,
            })

        for tipo, lista in sorted(por_tipo.items()):
            print(f"  --- {tipo} ({len(lista)}) ---")
            for c in lista[:15]:
                status = "ON" if c['oper'] == '1' else "off"
                tele = "TEL" if c['tele'] == '1' else "---"
                print(f"    {c['codigo']:12s} | {c['nome'][:40]:40s} | {c['municipio']:20s} | {status} {tele}")
            if len(lista) > 15:
                print(f"    ... + {len(lista)-15} outras")
            print()

if __name__ == "__main__":
    main()
