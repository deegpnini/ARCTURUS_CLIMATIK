#!/usr/bin/env python3
"""
Consolida arquivos *_RECUPERADO.csv deduplicando por DATA.
1 registro por dia (prefere DATA_LEITURA > DATA_ULTIMA_ATUALIZACAO).
Valida contra dias do ano.
"""
import csv, os
from collections import defaultdict
from datetime import datetime

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
ANOS = [1939, 2012, 2013, 2014, 2023, 2024, 2025]

def dias_esperados(ano):
    if ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0):
        return 366
    return 365

def ler_e_deduplicar(ano):
    """Le CSV e retorna dict {data: (cota, filtro)} com 1 por dia."""
    path = f"{CACHE}/cotas_84580000_{ano}_RECUPERADO.csv"
    if not os.path.exists(path):
        return {}

    # Guarda candidatos por data
    candidatos = defaultdict(list)

    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data = (row.get('data') or '').strip()
            if not data or len(data) < 10:
                continue
            # Verifica se é do ano esperado
            if not data.startswith(str(ano)):
                continue
            cota_str = (row.get('cota') or '').strip()
            filtro = (row.get('filtro') or '').strip()
            if not cota_str:
                continue
            try:
                cota = float(cota_str)
            except:
                continue
            candidatos[data].append((filtro, cota))

    # Deduplica: prefere DATA_LEITURA > DATA_ULTIMA_ATUALIZACAO > resto
    result = {}
    for data, lista in candidatos.items():
        # Ordena: DATA_LEITURA primeiro
        lista.sort(key=lambda x: (0 if x[0] == 'DATA_LEITURA' else 1, -x[1]))
        filtro_vencedor, cota_vencedor = lista[0]
        result[data] = (cota_vencedor, filtro_vencedor)

    return result

def main():
    print("="*70)
    print("CONSOLIDACAO v2 (deduplicado por DATA) — 84580000")
    print("="*70)

    consolidado = []
    total_geral = 0
    total_esperado_geral = 0

    for ano in ANOS:
        esp = dias_esperados(ano)
        dados = ler_e_deduplicar(ano)
        n = len(dados)

        if n > esp:
            print(f"\n{ano}: ERRO! {n} dias > {esp} esperados")
            continue

        cob = (n / esp * 100) if esp else 0
        print(f"\n{ano}: {n}/{esp} ({cob:.1f}%)")

        for data in sorted(dados.keys()):
            cota, filtro = dados[data]
            consolidado.append(f"{data},{cota:.2f},84580000,{filtro}")

        total_geral += n
        total_esperado_geral += esp

    print()
    print("="*70)
    print(f"TOTAL: {total_geral}/{total_esperado_geral} ({total_geral/total_esperado_geral*100:.1f}%)")
    print("="*70)

    out = f"{CACHE}/cotas_84580000_RECUPERADOS_V2.csv"
    with open(out, 'w') as f:
        f.write("data,cota,fonte,filtro\n")
        f.write('\n'.join(consolidado))
    print(f"\nSalvo: {out}")

if __name__ == "__main__":
    main()
