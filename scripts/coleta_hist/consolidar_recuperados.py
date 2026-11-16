#!/usr/bin/env python3
"""
Consolida arquivos *_RECUPERADO.csv com dedupe por DATA.
Regra: para mesmo dia, prefere max(data) ou fonte DATA_LEITURA.
Gera CSV consolidado + relatorio de cobertura.
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

def ler_recuperado(ano):
    """Le CSV recuperado, retorna dict {data: (cota, fonte)}"""
    path = f"{CACHE}/cotas_84580000_{ano}_RECUPERADO.csv"
    if not os.path.exists(path):
        return {}
    dados = {}
    with open(path) as f:
        reader = csv.DictReader(f)
        for row in reader:
            data = row.get('data', '').strip()
            if not data: continue
            cota = row.get('cota', '').strip()
            fonte = row.get('fonte', '').strip()
            filtro = row.get('filtro', '').strip()
            if not cota: continue
            try:
                v = float(cota)
            except:
                continue
            # Prefere DATA_LEITURA, depois mantem maior
            atual = dados.get(data)
            if atual is None:
                dados[data] = (v, fonte, filtro)
            else:
                # Prioridade: DATA_LEITURA > DATA_ULTIMA_ATUALIZACAO
                if filtro == 'DATA_LEITURA' and atual[2] != 'DATA_LEITURA':
                    dados[data] = (v, fonte, filtro)
    return dados

def main():
    print("="*70)
    print("CONSOLIDACAO + DEDUPLICACAO — 84580000")
    print("="*70)

    total_dias = 0
    total_esperado = 0
    consolidado = []

    for ano in ANOS:
        esp = dias_esperados(ano)
        dados = ler_recuperado(ano)
        
        # Dedupe efetivo
        dias_unicos = len(dados)
        cob = (dias_unicos / esp * 100) if esp else 0
        
        print(f"\n{ano}:")
        print(f"  Esperado: {esp} dias")
        print(f"  Unicos:   {dias_unicos} dias ({cob:.1f}%)")
        
        for data in sorted(dados.keys()):
            v, fonte, filtro = dados[data]
            consolidado.append(f"{data},{v:.2f},{fonte},{filtro},{ano}")
        
        total_dias += dias_unicos
        total_esperado += esp

    print()
    print("="*70)
    print(f"TOTAL: {total_dias}/{total_esperado} ({total_dias/total_esperado*100:.1f}%)")
    print("="*70)

    # Salva consolidado
    out = f"{CACHE}/cotas_84580000_RECUPERADOS_CONSOLIDADO.csv"
    with open(out, 'w') as f:
        f.write("data,cota,fonte,filtro,ano\n")
        f.write('\n'.join(consolidado))
    print(f"\nSalvo: {out}")

if __name__ == "__main__":
    main()
