#!/usr/bin/env python3
"""
Baseline SEM dependencias pesadas.
Usa apenas Python puro + numpy se disponivel.
Se nao tiver numpy, usa listas.
"""
import csv, os, sys
from datetime import datetime
from collections import defaultdict
import math

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

try:
    import numpy as np
    TEM_NUMPY = True
except ImportError:
    TEM_NUMPY = False
    print("(numpy nao disponivel, usando Python puro)")

def carregar(horizonte):
    arquivo = f"{CACHE}/dataset_{horizonte}.csv"
    rows = list(csv.DictReader(open(arquivo)))
    return rows

def preparar(rows, horizonte):
    cols_remover = {'timestamp', f'target_{horizonte}'}
    cols = [c for c in rows[0].keys() if c not in cols_remover]
    
    X = []
    y = []
    ts = []
    for r in rows:
        t = r.get(f'target_{horizonte}', '')
        if not t: continue
        try: yv = float(t)
        except: continue
        
        xv = []
        for c in cols:
            v = r.get(c, '')
            if v == '':
                xv.append(None)
            else:
                try: xv.append(float(v))
                except: xv.append(None)
        
        X.append(xv)
        y.append(yv)
        ts.append(r['timestamp'])
    
    return X, y, ts, cols

def baseline_persistencia(X, y, cols):
    """Baseline: prever y = cota atual."""
    idx_cota = cols.index('cota')
    erros = []
    for i, x in enumerate(X):
        cota_atual = x[idx_cota]
        if cota_atual is None: continue
        erros.append(abs(cota_atual - y[i]))
    return sum(erros)/len(erros) if erros else 0

def baseline_media_movel(X, y, cols, janela=4):
    """Baseline: prever y = media das ultimas N cotas."""
    idx_cota = cols.index('cota')
    erros = []
    for i, x in enumerate(X):
        vals = []
        for j in range(i, max(0, i-janela), -1):
            v = X[j][idx_cota] if j < len(X) else None
            if v is not None: vals.append(v)
        if not vals: continue
        pred = sum(vals) / len(vals)
        erros.append(abs(pred - y[i]))
    return sum(erros)/len(erros) if erros else 0

def main():
    for h in ['1h', '3h', '6h']:
        print("="*70)
        print(f"HORIZONTE {h}")
        print("="*70)
        
        rows = carregar(h)
        X, y, ts, cols = preparar(rows, h)
        print(f"Exemplos: {len(X)}")
        
        # Split temporal
        idx_treino = [i for i, t in enumerate(ts) if t < '2025-09-01']
        idx_val = [i for i, t in enumerate(ts) if '2025-09-01' <= t < '2026-07-01']
        idx_teste = [i for i, t in enumerate(ts) if t >= '2026-07-01']
        
        print(f"Treino: {len(idx_treino)} | Val: {len(idx_val)} | Teste: {len(idx_teste)}")
        print()
        
        # Baseline 1: persistencia
        mae_persist_treino = baseline_persistencia([X[i] for i in idx_treino], [y[i] for i in idx_treino], cols)
        mae_persist_val = baseline_persistencia([X[i] for i in idx_val], [y[i] for i in idx_val], cols)
        mae_persist_teste = baseline_persistencia([X[i] for i in idx_teste], [y[i] for i in idx_teste], cols)
        
        # Baseline 2: media movel
        mae_mm_treino = baseline_media_movel(X[:max(idx_treino)+1], y[:max(idx_treino)+1], cols)
        
        print("=== BASELINE PERSISTENCIA (y_pred = cota_atual) ===")
        print(f"MAE treino: {mae_persist_treino:.2f} cm")
        print(f"MAE val:    {mae_persist_val:.2f} cm")
        print(f"MAE teste:  {mae_persist_teste:.2f} cm")
        print()
        
        print("=== BASELINE MEDIA MOVEL (y_pred = media ultimas 4 cotas) ===")
        print(f"MAE treino: {mae_mm_treino:.2f} cm")
        print()
        
        # Estatisticas do target
        vals_y = [y[i] for i in range(len(y))]
        vals_y.sort()
        p50 = vals_y[len(vals_y)//2]
        p90 = vals_y[int(len(vals_y)*0.9)]
        p99 = vals_y[int(len(vals_y)*0.99)]
        print("=== TARGET ===")
        print(f"P50: {p50:.2f} | P90: {p90:.2f} | P99: {p99:.2f} | Max: {vals_y[-1]:.2f}")
        print()
        print("=== INTERPRETACAO ===")
        print(f"Persistencia MAE teste = {mae_persist_teste:.2f} cm")
        print(f"P50 do target = {p50:.2f} cm")
        if mae_persist_teste < p50 * 0.3:
            print("-> persistencia JA e' forte (rio estavel)")
        else:
            print("-> persistencia e' fraca, modelo ML pode ganhar")
        print()

if __name__ == "__main__":
    main()
