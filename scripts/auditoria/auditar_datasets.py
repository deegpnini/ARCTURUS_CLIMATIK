#!/usr/bin/env python3
"""
Auditoria dos 3 datasets supervisionados.
"""
import csv, os
from collections import defaultdict
from datetime import datetime

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def auditar(arquivo, horizonte):
    print("="*70)
    print(f"DATASET {horizonte}")
    print(f"Arquivo: {arquivo}")
    print("="*70)

    with open(arquivo) as f:
        rows = list(csv.DictReader(f))

    n = len(rows)
    print(f"Total de linhas: {n}")

    if not rows: return

    # Periodo
    datas = [r['timestamp'] for r in rows]
    print(f"Periodo: {datas[0]} a {datas[-1]}")

    # NaN por coluna
    print()
    print("=== NaN POR COLUNA ===")
    colunas = list(rows[0].keys())
    for col in colunas:
        if col in ('timestamp',): continue
        n_nan = sum(1 for r in rows if r[col] == '')
        pct = n_nan / n * 100
        if pct > 0:
            print(f"  {col:25s} {n_nan:7d} ({pct:5.1f}%)")

    # Target: distribuicao
    target_col = f'target_{horizonte}'
    valores = []
    for r in rows:
        v = r.get(target_col, '')
        if v:
            try: valores.append(float(v))
            except: pass

    print()
    print(f"=== TARGET {target_col} ===")
    print(f"Valores: {len(valores)}")
    if valores:
        valores.sort()
        def pct(p):
            idx = int(len(valores) * p)
            return valores[min(idx, len(valores)-1)]
        print(f"Min:  {valores[0]:.2f}")
        print(f"P25:  {pct(0.25):.2f}")
        print(f"P50:  {pct(0.50):.2f}")
        print(f"P75:  {pct(0.75):.2f}")
        print(f"P90:  {pct(0.90):.2f}")
        print(f"P95:  {pct(0.95):.2f}")
        print(f"P99:  {pct(0.99):.2f}")
        print(f"Max:  {valores[-1]:.2f}")

        # Densidade de extremos
        p90 = pct(0.90)
        p95 = pct(0.95)
        p99 = pct(0.99)
        print()
        print("=== DENSIDADE DE EXTREMOS ===")
        print(f"> P90: {sum(1 for v in valores if v > p90)} ({sum(1 for v in valores if v > p90)/len(valores)*100:.2f}%)")
        print(f"> P95: {sum(1 for v in valores if v > p95)} ({sum(1 for v in valores if v > p95)/len(valores)*100:.2f}%)")
        print(f"> P99: {sum(1 for v in valores if v > p99)} ({sum(1 for v in valores if v > p99)/len(valores)*100:.2f}%)")

    # Distribuicao por mes
    print()
    print("=== LINHAS POR MES ===")
    por_mes = defaultdict(int)
    for r in rows:
        mes = r['timestamp'][:7]
        por_mes[mes] += 1
    for mes in sorted(por_mes.keys()):
        n_mes = por_mes[mes]
        flag = "⚠️" if n_mes < 500 else ""
        print(f"  {mes}: {n_mes:6d} {flag}")

    print()

def main():
    for h in ['1h', '3h', '6h']:
        arquivo = f"{CACHE}/dataset_{h}.csv"
        if os.path.exists(arquivo):
            auditar(arquivo, h)

if __name__ == "__main__":
    main()
