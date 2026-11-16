#!/usr/bin/env python3
"""
Split por EVENTO inteiro, nao por data.
Resolve o problema do gap jan-abr/2026.
"""
import csv, json, os
from datetime import datetime
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def detectar_eventos(rows, limiar, gap_min=120):
    eventos = []
    ev = None
    ultima = None
    for r in rows:
        v = r.get('cota', '')
        if not v: continue
        try: c = float(v)
        except: continue
        try: dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
        except: continue
        if c > limiar:
            if ev is None:
                ev = {'inicio': dt, 'fim': dt, 'leituras': 1, 'pico': c}
            else:
                gap = (dt - ultima).total_seconds() / 60 if ultima else 0
                if gap > gap_min:
                    eventos.append(ev)
                    ev = {'inicio': dt, 'fim': dt, 'leituras': 1, 'pico': c}
                else:
                    ev['fim'] = dt
                    ev['leituras'] += 1
                    ev['pico'] = max(ev['pico'], c)
            ultima = dt
        else:
            if ev: eventos.append(ev); ev = None
            ultima = dt
    if ev: eventos.append(ev)
    return eventos

def main():
    for h in ['1h', '3h', '6h']:
        rows = list(csv.DictReader(open(f"{CACHE}/dataset_{h}.csv")))
        
        # Cota P95
        cotas = []
        for r in rows:
            v = r.get('cota', '')
            if v:
                try: cotas.append(float(v))
                except: pass
        cotas.sort()
        p95 = cotas[int(len(cotas)*0.95)]
        
        eventos = detectar_eventos(rows, p95)
        
        print(f"\n=== {h}: {len(eventos)} eventos P95 ===")
        
        # Divide 70/15/15
        n = len(eventos)
        n_treino = int(n * 0.70)
        n_val = int(n * 0.15)
        
        treino = eventos[:n_treino]
        val = eventos[n_treino:n_treino+n_val]
        teste = eventos[n_treino+n_val:]
        
        def resumo(nome, evs):
            if not evs: 
                print(f"  {nome}: vazio")
                return
            total_leit = sum(e['leituras'] for e in evs)
            print(f"  {nome}: {len(evs)} eventos, {total_leit} leituras")
            print(f"    Periodo: {evs[0]['inicio']} a {evs[-1]['fim']}")
        
        resumo("Treino", treino)
        resumo("Val", val)
        resumo("Teste", teste)
        
        # Salva split
        split = {
            'horizonte': h,
            'limiar': p95,
            'treino': [{'inicio': e['inicio'].isoformat(), 'fim': e['fim'].isoformat()} for e in treino],
            'val': [{'inicio': e['inicio'].isoformat(), 'fim': e['fim'].isoformat()} for e in val],
            'teste': [{'inicio': e['inicio'].isoformat(), 'fim': e['fim'].isoformat()} for e in teste],
        }
        with open(f"{CACHE}/split_{h}.json", 'w') as f:
            json.dump(split, f, indent=2, default=str)
        print(f"  Salvo: {CACHE}/split_{h}.json")

if __name__ == "__main__":
    main()
