#!/usr/bin/env python3
"""
Split treino/validacao/teste por EVENTO INTEIRO.
Nenhum evento cruza fronteiras.
"""
import csv, os
from datetime import datetime
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def detectar_eventos(rows, limiar):
    """Mesmo algoritmo de antes."""
    eventos = []
    evento_atual = None
    ultima_data = None
    
    for r in rows:
        cota_str = r.get('target_1h', '')
        if not cota_str: continue
        try: cota = float(cota_str)
        except: continue
        try:
            dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
        except: continue
        
        if cota > limiar:
            if evento_atual is None:
                evento_atual = {'inicio': dt, 'fim': dt, 'leituras': 1, 'linhas_idx': [len(eventos)]}
            else:
                gap = (dt - ultima_data).total_seconds() / 60 if ultima_data else 0
                if gap > 120:
                    eventos.append(evento_atual)
                    evento_atual = {'inicio': dt, 'fim': dt, 'leituras': 1, 'linhas_idx': []}
                else:
                    evento_atual['fim'] = dt
                    evento_atual['leituras'] += 1
            ultima_data = dt
        else:
            if evento_atual is not None:
                eventos.append(evento_atual)
                evento_atual = None
            ultima_data = dt
    if evento_atual is not None:
        eventos.append(evento_atual)
    return eventos

def main():
    arquivo = f"{CACHE}/dataset_1h.csv"
    with open(arquivo) as f:
        rows = list(csv.DictReader(f))
    
    print(f"Total de linhas: {len(rows)}")
    
    # Usa P95 como limiar de evento
    valores = []
    for r in rows:
        t = r.get('target_1h', '')
        if t:
            try: valores.append(float(t))
            except: pass
    valores.sort()
    p95 = valores[int(len(valores)*0.95)]
    
    print(f"Limiar P95: {p95:.2f}")
    print()
    
    eventos = detectar_eventos(rows, p95)
    print(f"Eventos detectados: {len(eventos)}")
    print()
    
    # Split por tempo (ja que eventos sao cronologicos)
    # 70% primeiros -> treino
    # 15% -> validacao
    # 15% -> teste
    n_treino = int(len(eventos) * 0.70)
    n_val = int(len(eventos) * 0.15)
    
    eventos_treino = eventos[:n_treino]
    eventos_val = eventos[n_treino:n_treino+n_val]
    eventos_teste = eventos[n_treino+n_val:]
    
    print("="*70)
    print("SPLIT POR EVENTO")
    print("="*70)
    print(f"Treino:     {len(eventos_treino)} eventos")
    print(f"  Periodo:  {eventos_treino[0]['inicio']} a {eventos_treino[-1]['fim']}")
    print(f"Validacao:  {len(eventos_val)} eventos")
    if eventos_val:
        print(f"  Periodo:  {eventos_val[0]['inicio']} a {eventos_val[-1]['fim']}")
    print(f"Teste:      {len(eventos_teste)} eventos")
    if eventos_teste:
        print(f"  Periodo:  {eventos_teste[0]['inicio']} a {eventos_teste[-1]['fim']}")
    
    # Salva split
    split = {
        'limiar': p95,
        'treino': [(e['inicio'].isoformat(), e['fim'].isoformat()) for e in eventos_treino],
        'validacao': [(e['inicio'].isoformat(), e['fim'].isoformat()) for e in eventos_val],
        'teste': [(e['inicio'].isoformat(), e['fim'].isoformat()) for e in eventos_teste],
    }
    
    import json
    out = f"{CACHE}/split_eventos.json"
    with open(out, 'w') as f:
        json.dump(split, f, indent=2, default=str)
    print()
    print(f"Split salvo: {out}")

if __name__ == "__main__":
    main()
