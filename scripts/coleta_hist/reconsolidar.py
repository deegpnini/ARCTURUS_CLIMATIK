#!/usr/bin/env python3
"""
Reconsolida usando SO DATA_LEITURA.
Ignora DATA_ULTIMA_ATUALIZACAO (que mistura anos).
"""
import csv, os
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
ANOS = [1939, 2012, 2013, 2014, 2023, 2024, 2025]

def dias_esperados(ano):
    if ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0):
        return 366
    return 365

def ler_apenas_leituras(ano):
    """So aceita registros com filtro=DATA_LEITURA e data no ano."""
    path = f"{CACHE}/cotas_84580000_{ano}_RECUPERADO.csv"
    if not os.path.exists(path):
        return {}

    dados = {}
    with open(path) as f:
        for row in csv.DictReader(f):
            filtro = (row.get('filtro') or '').strip()
            if filtro != 'DATA_LEITURA':
                continue
            data = (row.get('data') or '').strip()
            if not data.startswith(str(ano)):
                continue
            cota_str = (row.get('cota') or '').strip()
            if not cota_str: continue
            try:
                cota = float(cota_str)
            except: continue
            dados[data] = cota
    return dados

def main():
    print("="*70)
    print("RECONSOLIDACAO (so DATA_LEITURA, valida ano) — 84580000")
    print("="*70)

    consolidado = ["data,cota,fonte"]
    total = 0
    total_esp = 0

    for ano in ANOS:
        esp = dias_esperados(ano)
        dados = ler_apenas_leituras(ano)
        n = len(dados)
        cob = (n / esp * 100) if esp else 0
        status = "OK" if n <= esp else f"ERRO (>{esp})"
        print(f"  {ano}: {n}/{esp} ({cob:.1f}%) {status}")

        for data in sorted(dados.keys()):
            consolidado.append(f"{data},{dados[data]:.2f},84580000")

        total += n
        total_esp += esp

    print()
    print(f"TOTAL: {total}/{total_esp} ({total/total_esp*100:.1f}%)")

    out = f"{CACHE}/cotas_84580000_LIMPO_v2.csv"
    with open(out, 'w') as f:
        f.write('\n'.join(consolidado))
    print(f"Salvo: {out}")

if __name__ == "__main__":
    main()
