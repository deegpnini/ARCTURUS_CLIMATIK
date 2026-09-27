#!/usr/bin/env python3
"""
Auditoria estatistica do split 18/4/5.
Analisa distribuicao por fold.
"""
import json
from datetime import datetime
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

# Carrega split_v3
with open(f"{CACHE}/split_v3.json") as f:
    split = json.load(f)

historicos = split['historico']
operacionais = split['operacional']

n_tr = len(split['treino_idx'])
n_va = len(split['val_idx'])

treino = historicos[:n_tr]
val = historicos[n_tr:n_tr+n_va]
teste = historicos[n_tr+n_va:]

print("="*100)
print("AUDITORIA ESTATISTICA DO SPLIT — 18/4/5")
print("="*100)

def analisar(fold, nome):
    print(f"\n{'='*100}")
    print(f"{nome} ({len(fold)} eventos)")
    print(f"{'='*100}")
    
    if not fold:
        print("  vazio")
        return None
    
    picos = [e['pico'] for e in fold]
    duracoes = [e['duracao_h'] for e in fold]
    n_picos = [e['n_picos'] for e in fold]
    
    # Datas
    datas_ini = [e['inicio'][:10] for e in fold]
    datas_fim = [e['fim'][:10] for e in fold]
    
    # Epoca do ano (mes)
    meses = [datetime.fromisoformat(e['inicio']).month for e in fold]
    mes_dist = defaultdict(int)
    for m in meses:
        mes_dist[m] += 1
    
    print(f"  Periodo: {datas_ini[0]} a {datas_fim[-1]}")
    print(f"  Pico max:  {max(picos):.1f}")
    print(f"  Pico min:  {min(picos):.1f}")
    print(f"  Pico med:  {sum(picos)/len(picos):.1f}")
    print(f"  Duracao max: {max(duracoes):.1f}h")
    print(f"  Duracao min: {min(duracoes):.1f}h")
    print(f"  Duracao med: {sum(duracoes)/len(duracoes):.1f}h")
    print(f"  N picos max: {max(n_picos)}")
    print(f"  N picos med: {sum(n_picos)/len(n_picos):.1f}")
    
    # Extremos
    P95_HIST = 141.0
    P99_HIST = 214.0
    n_p95 = sum(1 for p in picos if p > P95_HIST)
    n_p99 = sum(1 for p in picos if p > P99_HIST)
    print(f"  Eventos > P95 (141): {n_p95}")
    print(f"  Eventos > P99 (214): {n_p99}")
    
    # Intensidade (pico / duracao)
    intensidades = [p/max(d,1) for p, d in zip(picos, duracoes)]
    print(f"  Intensidade med: {sum(intensidades)/len(intensidades):.2f} cm/h")
    
    # Meses
    print(f"  Distribuicao por mes:")
    for m in sorted(mes_dist.keys()):
        print(f"    mes {m:02d}: {mes_dist[m]} eventos")
    
    return {
        'n': len(fold),
        'pico_max': max(picos),
        'pico_med': sum(picos)/len(picos),
        'dur_med': sum(duracoes)/len(duracoes),
        'n_p95': n_p95,
        'n_p99': n_p99,
        'meses': dict(mes_dist),
    }

r_tr = analisar(treino, "TREINO")
r_va = analisar(val, "VALIDACAO")
r_te = analisar(teste, "TESTE")
r_op = analisar(operacionais, "OPERACIONAL (21/09)")

# Analise comparativa
print()
print("="*100)
print("ANALISE COMPARATIVA")
print("="*100)
print(f"{'Metrica':25s} | {'Treino':10s} | {'Val':10s} | {'Teste':10s} | {'Oper':10s}")
print("-"*100)

def get(r, k, fmt="{:.1f}"):
    if r is None or k not in r: return "-"
    v = r[k]
    if isinstance(v, (int, float)):
        return fmt.format(v)
    return str(v)

print(f"{'N eventos':25s} | {get(r_tr,'n','{}'):10s} | {get(r_va,'n','{}'):10s} | {get(r_te,'n','{}'):10s} | {get(r_op,'n','{}'):10s}")
print(f"{'Pico max (cm)':25s} | {get(r_tr,'pico_max'):10s} | {get(r_va,'pico_max'):10s} | {get(r_te,'pico_max'):10s} | {get(r_op,'pico_max'):10s}")
print(f"{'Pico medio (cm)':25s} | {get(r_tr,'pico_med'):10s} | {get(r_va,'pico_med'):10s} | {get(r_te,'pico_med'):10s} | {get(r_op,'pico_med'):10s}")
print(f"{'Duracao media (h)':25s} | {get(r_tr,'dur_med'):10s} | {get(r_va,'dur_med'):10s} | {get(r_te,'dur_med'):10s} | {get(r_op,'dur_med'):10s}")
print(f"{'Eventos > P95':25s} | {get(r_tr,'n_p95','{}'):10s} | {get(r_va,'n_p95','{}'):10s} | {get(r_te,'n_p95','{}'):10s} | {get(r_op,'n_p95','{}'):10s}")
print(f"{'Eventos > P99':25s} | {get(r_tr,'n_p99','{}'):10s} | {get(r_va,'n_p99','{}'):10s} | {get(r_te,'n_p99','{}'):10s} | {get(r_op,'n_p99','{}'):10s}")

# Avaliacao
print()
print("="*100)
print("VEREDITO")
print("="*100)

problemas = []

if r_va and r_te:
    # Teste tem pelo menos 1 evento > P99?
    if r_te['n_p99'] == 0:
        problemas.append("Teste sem evento > P99 (subestima extremos)")
    
    # Validacao tem pelo menos 1 evento > P99?
    if r_va['n_p99'] == 0:
        problemas.append("Validacao sem evento > P99")
    
    # Treino tem eventos > P99?
    if r_tr['n_p99'] < 2:
        problemas.append(f"Treino com poucos eventos > P99 ({r_tr['n_p99']})")

if problemas:
    print("PROBLEMAS:")
    for p in problemas:
        print(f"  ⚠️ {p}")
else:
    print("✓ Distribuicao aceitavel")
    print("  - Treino tem eventos extremos")
    print("  - Validacao tem eventos extremos")
    print("  - Teste tem eventos extremos")
