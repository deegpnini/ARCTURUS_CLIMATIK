#!/usr/bin/env python3
"""
AUDITORIA PRÉ-TREINAMENTO — Passo 3
5 blocos por dataset: cobertura, cota, eventos, integridade, split.
"""
import csv, os, json
from datetime import datetime, timedelta
from collections import defaultdict, Counter

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

# ============================================================
# BLOCO 1 — COBERTURA TEMPORAL
# ============================================================
def bloco_cobertura(rows, nome):
    print(f"\n{'='*70}")
    print(f"BLOCO 1 — COBERTURA TEMPORAL | {nome}")
    print(f"{'='*70}")
    
    datas = [r['timestamp'] for r in rows]
    print(f"  Primeira: {datas[0]}")
    print(f"  Ultima:   {datas[-1]}")
    print(f"  Total:    {len(rows)} linhas")
    
    por_mes = defaultdict(int)
    for d in datas:
        por_mes[d[:7]] += 1
    
    print(f"\n  Linhas por mes:")
    meses_fracos = []
    for mes in sorted(por_mes.keys()):
        n = por_mes[mes]
        flag = ""
        if n < 500:
            flag = " ⚠️"
            meses_fracos.append(mes)
        print(f"    {mes}: {n:6d}{flag}")
    
    # Maiores intervalos sem dados (linhas consecutivas com gap > 6h)
    gaps = []
    for i in range(1, len(datas)):
        d1 = datetime.strptime(datas[i-1], "%Y-%m-%d %H:%M:%S")
        d2 = datetime.strptime(datas[i], "%Y-%m-%d %H:%M:%S")
        delta_h = (d2 - d1).total_seconds() / 3600
        if delta_h > 6:
            gaps.append((datas[i-1], datas[i], delta_h))
    
    print(f"\n  Maiores intervalos sem dados (>6h): {len(gaps)}")
    for g in sorted(gaps, key=lambda x: -x[2])[:5]:
        print(f"    {g[0]} -> {g[1]} ({g[2]:.1f}h)")
    
    return {'meses_fracos': meses_fracos, 'n_gaps': len(gaps)}

# ============================================================
# BLOCO 2 — DISTRIBUIÇÃO DA COTA
# ============================================================
def bloco_cota(rows, nome, horizonte):
    print(f"\n{'='*70}")
    print(f"BLOCO 2 — DISTRIBUICAO DA COTA | {nome}")
    print(f"{'='*70}")
    
    # Usa o target como referencia (cota futura)
    target_col = f'target_{horizonte}'
    valores = []
    for r in rows:
        v = r.get(target_col, '')
        if v:
            try: valores.append(float(v))
            except: pass
    
    valores.sort()
    n = len(valores)
    def pct(p):
        return valores[min(int(n * p), n-1)]
    
    print(f"  Valores: {n}")
    print(f"  Min:  {valores[0]:.2f}")
    print(f"  P25:  {pct(0.25):.2f}")
    print(f"  P50:  {pct(0.50):.2f}")
    print(f"  P75:  {pct(0.75):.2f}")
    print(f"  P90:  {pct(0.90):.2f}")
    print(f"  P95:  {pct(0.95):.2f}")
    print(f"  P99:  {pct(0.99):.2f}")
    print(f"  Max:  {valores[-1]:.2f}")
    
    return {'P90': pct(0.90), 'P95': pct(0.95), 'P99': pct(0.99), 'valores': valores}

# ============================================================
# BLOCO 3 — EVENTOS HIDROLÓGICOS
# ============================================================
def detectar_eventos(rows, limiar, gap_min=120):
    eventos = []
    evento_atual = None
    ultima_data = None
    
    for r in rows:
        v = r.get('cota', '')
        if not v: continue
        try: cota = float(v)
        except: continue
        try: dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
        except: continue
        
        if cota > limiar:
            if evento_atual is None:
                evento_atual = {'inicio': dt, 'fim': dt, 'leituras': 1, 'pico': cota}
            else:
                gap = (dt - ultima_data).total_seconds() / 60 if ultima_data else 0
                if gap > gap_min:
                    eventos.append(evento_atual)
                    evento_atual = {'inicio': dt, 'fim': dt, 'leituras': 1, 'pico': cota}
                else:
                    evento_atual['fim'] = dt
                    evento_atual['leituras'] += 1
                    evento_atual['pico'] = max(evento_atual['pico'], cota)
            ultima_data = dt
        else:
            if evento_atual is not None:
                eventos.append(evento_atual)
                evento_atual = None
            ultima_data = dt
    if evento_atual is not None:
        eventos.append(evento_atual)
    return eventos

def bloco_eventos(rows, nome, p90, p95, p99):
    print(f"\n{'='*70}")
    print(f"BLOCO 3 — EVENTOS HIDROLOGICOS | {nome}")
    print(f"{'='*70}")
    
    for label, limiar in [('P90', p90), ('P95', p95), ('P99', p99)]:
        eventos = detectar_eventos(rows, limiar)
        print(f"\n  Limiar {label} ({limiar:.2f}): {len(eventos)} eventos")
        if eventos:
            duracoes = [(e['fim'] - e['inicio']).total_seconds() / 3600 for e in eventos]
            print(f"    Duracao media: {sum(duracoes)/len(duracoes):.1f}h")
            print(f"    Duracao max:   {max(duracoes):.1f}h")
            print(f"    Total leituras: {sum(e['leituras'] for e in eventos)}")
            
            # Eventos por ano
            por_ano = defaultdict(int)
            for e in eventos:
                por_ano[e['inicio'].year] += 1
            print(f"    Por ano: {dict(sorted(por_ano.items()))}")
            
            # Maior evento
            maior = max(eventos, key=lambda x: x['pico'])
            print(f"    Maior evento: {maior['inicio']} a {maior['fim']} (pico {maior['pico']:.1f})")

# ============================================================
# BLOCO 4 — INTEGRIDADE
# ============================================================
def bloco_integridade(rows, nome):
    print(f"\n{'='*70}")
    print(f"BLOCO 4 — INTEGRIDADE | {nome}")
    print(f"{'='*70}")
    
    # Duplicatas
    ts = [r['timestamp'] for r in rows]
    dup = len(ts) - len(set(ts))
    print(f"  Duplicatas: {dup}")
    
    # Timestamps fora da grade 15min
    fora = 0
    for t in ts:
        try:
            dt = datetime.strptime(t, "%Y-%m-%d %H:%M:%S")
            if dt.minute % 15 != 0:
                fora += 1
        except:
            fora += 1
    print(f"  Timestamps fora da grade 15min: {fora}")
    
    # NaN por coluna (so as que tem)
    print(f"\n  NaN por coluna (top 15):")
    nan_por_col = {}
    for c in rows[0].keys():
        if c == 'timestamp': continue
        n_nan = sum(1 for r in rows if r.get(c, '') == '')
        pct = n_nan / len(rows) * 100
        if pct > 0:
            nan_por_col[c] = pct
    
    for c, pct in sorted(nan_por_col.items(), key=lambda x: -x[1])[:15]:
        print(f"    {c:25s} {pct:5.1f}%")
    
    # Targets ausentes
    print(f"\n  Targets ausentes:")
    for c in rows[0].keys():
        if c.startswith('target_'):
            n_nan = sum(1 for r in rows if r.get(c, '') == '')
            print(f"    {c}: {n_nan}")
    
    return {'duplicatas': dup, 'fora_grade': fora, 'nan_cols': nan_nan_col if False else nan_por_col}

# ============================================================
# BLOCO 5 — SEPARAÇÃO TEMPORAL
# ============================================================
def bloco_split(rows, nome):
    print(f"\n{'='*70}")
    print(f"BLOCO 5 — SEPARACAO TEMPORAL | {nome}")
    print(f"{'='*70}")
    
    # Proposta de corte (sem fixar)
    corte_treino = '2025-09-01'
    corte_val = '2026-07-01'
    
    n_treino = sum(1 for r in rows if r['timestamp'] < corte_treino)
    n_val = sum(1 for r in rows if corte_treino <= r['timestamp'] < corte_val)
    n_teste = sum(1 for r in rows if r['timestamp'] >= corte_val)
    
    total = len(rows)
    print(f"  Corte proposto:")
    print(f"    Treino:    < {corte_treino}")
    print(f"    Validacao: {corte_treino} a {corte_val}")
    print(f"    Teste:     >= {corte_val}")
    print()
    print(f"  Distribuicao:")
    print(f"    Treino:    {n_treino:6d} ({n_treino/total*100:.1f}%)")
    print(f"    Validacao: {n_val:6d} ({n_val/total*100:.1f}%)")
    print(f"    Teste:     {n_teste:6d} ({n_teste/total*100:.1f}%)")

# ============================================================
# MAIN
# ============================================================
def main():
    for h in ['1h', '3h', '6h']:
        arquivo = f"{CACHE}/dataset_{h}.csv"
        if not os.path.exists(arquivo): continue
        rows = list(csv.DictReader(open(arquivo)))
        nome = f"dataset_{h}"
        
        print(f"\n\n{'#'*70}")
        print(f"# {nome} | {len(rows)} linhas")
        print(f"{'#'*70}")
        
        bloco_cobertura(rows, nome)
        cota_info = bloco_cota(rows, nome, h)
        bloco_eventos(rows, nome, cota_info['P90'], cota_info['P95'], cota_info['P99'])
        bloco_integridade(rows, nome)
        bloco_split(rows, nome)

if __name__ == "__main__":
    main()
