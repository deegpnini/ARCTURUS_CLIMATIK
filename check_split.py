#!/usr/bin/env python3
"""
3 verificacoes do split:
1. Eventos fragmentados?
2. Quais eventos no teste?
3. Val tem amostra suficiente?
"""
import csv, json, os
from datetime import datetime, timedelta
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def detectar_eventos(rows, limiar, gap_min=120):
    eventos = []
    ev = None
    ultima = None
    idx_inicio = None
    for i, r in enumerate(rows):
        v = r.get('cota', '')
        if not v: continue
        try: c = float(v)
        except: continue
        try: dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
        except: continue
        if c > limiar:
            if ev is None:
                ev = {'inicio': dt, 'fim': dt, 'leituras': 1, 'pico': c}
                idx_inicio = i
            else:
                gap = (dt - ultima).total_seconds() / 60 if ultima else 0
                if gap > gap_min:
                    eventos.append(ev)
                    ev = {'inicio': dt, 'fim': dt, 'leituras': 1, 'pico': c}
                    idx_inicio = i
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
    for h in ['1h']:
        rows = list(csv.DictReader(open(f"{CACHE}/dataset_{h}.csv")))
        cotas = [float(r['cota']) for r in rows if r.get('cota')]
        cotas.sort()
        p95 = cotas[int(len(cotas)*0.95)]

        print("="*70)
        print(f"VERIFICACAO 1 — EVENTOS FRAGMENTADOS? | {h}")
        print("="*70)
        print(f"Limiar P95: {p95:.2f}")

        # Detecta com gap_min=120 (atual) e com gap_min=360 (conservador)
        ev_120 = detectar_eventos(rows, p95, 120)
        ev_360 = detectar_eventos(rows, p95, 360)

        print(f"Eventos com gap_min=120: {len(ev_120)}")
        print(f"Eventos com gap_min=360: {len(ev_360)}")
        diff = len(ev_120) - len(ev_360)
        if diff > 0:
            print(f"-> {diff} eventos se FUNDEM com gap maior")
            print(f"-> indica fragmentacao artificial")
        else:
            print(f"-> sem fragmentacao: gap_min nao muda contagem")

        print()
        print("="*70)
        print(f"VERIFICACAO 2 — EVENTOS NO TESTE | {h}")
        print("="*70)
        split = json.load(open(f"{CACHE}/split_{h}.json"))
        print(f"Corte teste: a partir de {split['teste'][0]['inicio'] if split['teste'] else 'n/a'}")
        print(f"Total eventos teste: {len(split['teste'])}")
        print()
        for i, ev in enumerate(split['teste'], 1):
            ini = ev['inicio'][:16]
            fim = ev['fim'][:16]
            print(f"  [{i}] {ini} -> {fim}")
        print()
        print(f"21/09/2026 esta no teste? ", end="")
        if any('2026-09-21' in ev['inicio'] or '2026-09-21' in ev['fim'] for ev in split['teste']):
            print("SIM")
        else:
            print("NAO")

        print()
        print("="*70)
        print(f"VERIFICACAO 3 — AMOSTRA DE VAL | {h}")
        print("="*70)
        print(f"Total val: {len(split['val'])} eventos")
        print()
        for i, ev in enumerate(split['val'], 1):
            ini = ev['inicio'][:16]
            fim = ev['fim'][:16]
            print(f"  [{i}] {ini} -> {fim}")

if __name__ == "__main__":
    main()
