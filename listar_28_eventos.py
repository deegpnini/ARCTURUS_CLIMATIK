#!/usr/bin/env python3
"""
Lista os 28 eventos V2 com detalhes.
Auxilia decisao de split.
"""
import csv, json
from datetime import datetime
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def detectar_eventos_v2(rows, p95, p75):
    eventos = []
    ev = None
    for r in rows:
        v = r.get('cota', '')
        if not v: continue
        try: cota = float(v)
        except: continue
        try: dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
        except: continue

        if cota > p95:
            if ev is None:
                ev = {'inicio': dt, 'fim': dt, 'pico': cota, 'leituras': 1}
            else:
                ev['fim'] = dt
                ev['leituras'] += 1
                if cota > ev['pico']:
                    ev['pico'] = cota
        else:
            if ev is not None:
                if cota < p75:
                    eventos.append(ev)
                    ev = None
                else:
                    ev['fim'] = dt
                    ev['leituras'] += 1
    if ev is not None:
        eventos.append(ev)
    return eventos

def main():
    arquivo = f"{CACHE}/dataset_1h.csv"
    rows = list(csv.DictReader(open(arquivo)))

    cotas = sorted([float(r['cota']) for r in rows if r.get('cota')])
    p75 = cotas[int(len(cotas)*0.75)]
    p95 = cotas[int(len(cotas)*0.95)]

    eventos = detectar_eventos_v2(rows, p95, p75)

    print("="*100)
    print(f"LISTA DOS {len(eventos)} EVENTOS V2 (P95 > {p95:.1f} cm)")
    print("="*100)
    print()
    print(f"{'#':3s} | {'Inicio':20s} | {'Fim':20s} | {'Dur':6s} | {'Pico':6s} | {'Leit':5s} | {'Ano':4s}")
    print("-"*100)

    for i, ev in enumerate(eventos, 1):
        dur = (ev['fim'] - ev['inicio']).total_seconds() / 3600
        print(f"{i:3d} | {ev['inicio'].strftime('%Y-%m-%d %H:%M'):20s} | "
              f"{ev['fim'].strftime('%Y-%m-%d %H:%M'):20s} | {dur:5.1f}h | "
              f"{ev['pico']:6.1f} | {ev['leituras']:5d} | {ev['inicio'].year}")

    # Distribuicao por ano
    print()
    print("="*100)
    print("DISTRIBUICAO POR ANO")
    print("="*100)
    por_ano = defaultdict(int)
    for e in eventos:
        por_ano[e['inicio'].year] += 1
    for ano in sorted(por_ano):
        print(f"  {ano}: {por_ano[ano]} eventos")

    # Proposta de split 70/15/15
    n = len(eventos)
    n_tr = int(n * 0.70)
    n_va = int(n * 0.15)
    print()
    print("="*100)
    print(f"SPLIT PROPOSTO (70/15/15)")
    print("="*100)
    print(f"  Treino:     {n_tr} eventos ({eventos[0]['inicio'].date()} a {eventos[n_tr-1]['fim'].date()})")
    print(f"  Validacao:  {n_va} eventos ({eventos[n_tr]['inicio'].date()} a {eventos[n_tr+n_va-1]['fim'].date()})")
    print(f"  Teste:      {n - n_tr - n_va} eventos ({eventos[n_tr+n_va]['inicio'].date()} a {eventos[-1]['fim'].date()})")
    print()
    print(f"  Teste inclui 21/09/2026? {'SIM' if any(e['inicio'].strftime('%Y-%m-%d') == '2026-09-21' or '2026-09-21' in e['inicio'].strftime('%Y-%m-%d') for e in eventos[n_tr+n_va:]) else 'NAO'}")

    # Salva
    out = {
        'p75': p75, 'p95': p95,
        'eventos': [{
            'inicio': e['inicio'].isoformat(),
            'fim': e['fim'].isoformat(),
            'pico': e['pico'],
            'leituras': e['leituras'],
        } for e in eventos]
    }
    with open(f"{CACHE}/eventos_v2_final.json", 'w') as f:
        json.dump(out, f, indent=2, default=str)
    print(f"\nSalvo: {CACHE}/eventos_v2_final.json")

if __name__ == "__main__":
    main()
