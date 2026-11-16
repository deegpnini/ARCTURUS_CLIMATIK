#!/usr/bin/env python3
"""
Teste diferenciado: remove tendencia pra isolar lag real.
"""
import json, statistics
from collections import defaultdict
from datetime import datetime, timedelta

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def parse_dt(s):
    if not s: return None
    try: return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except: return None

def parse_num(s):
    if s is None: return None
    s = str(s).strip().replace(',', '.')
    if not s: return None
    try: return float(s)
    except: return None

def load():
    d = json.load(open(f"{CACHE}/ana_cadeia_tubarao_7d.json"))
    por_est = defaultdict(list)
    for it in d.get('items', []):
        dt = parse_dt(it.get('Data_Hora_Medicao'))
        if not dt: continue
        por_est[it.get('codigoestacao')].append({
            'dt': dt,
            'chuva': parse_num(it.get('Chuva_Adotada')),
            'vazao': parse_num(it.get('Vazao_Adotada')),
        })
    for cod in por_est: por_est[cod].sort(key=lambda x: x['dt'])
    return por_est

def serie_horaria(leituras, campo, agregacao='media'):
    buckets = defaultdict(list)
    for l in leituras:
        if l[campo] is not None:
            h = l['dt'].replace(minute=0, second=0, microsecond=0)
            buckets[h].append(l[campo])
    if agregacao == 'media':
        return {h: sum(v)/len(v) for h, v in buckets.items()}
    elif agregacao == 'soma':
        return {h: sum(v) for h, v in buckets.items()}
    elif agregacao == 'ultimo':
        return {h: v[-1] for h, v in buckets.items()}

def diferenciar(serie):
    horas = sorted(serie.keys())
    return {
        horas[i]: serie[horas[i]] - serie[horas[i-1]]
        for i in range(1, len(horas))
    }

def testar_lag(chuva_orleans, vazao_pouso, max_lag=48, nome=""):
    if len(chuva_orleans) < 5 or len(vazao_pouso) < 5:
        print(f"  {nome}: dados insuficientes")
        return None
    
    horas_comuns = sorted(set(chuva_orleans) | set(vazao_pouso))
    resultados = {}
    
    for lag in range(0, max_lag + 1):
        pares = []
        for h in horas_comuns:
            h_ef = h + timedelta(hours=lag)
            if h in chuva_orleans and h_ef in vazao_pouso:
                pares.append((chuva_orleans[h], vazao_pouso[h_ef]))
        
        if len(pares) >= 5:
            xs = [p[0] for p in pares]
            ys = [p[1] for p in pares]
            if len(set(xs)) < 2 or len(set(ys)) < 2:
                continue
            try:
                r = statistics.correlation(xs, ys)
                resultados[lag] = (r, len(pares))
            except: pass
    
    if not resultados:
        print(f"  {nome}: sem pares sobrepostos")
        return None
    
    top = sorted(resultados.items(), key=lambda x: -abs(x[1][0]))[:5]
    print(f"\n=== {nome} ===")
    print(f"  Top 5 lags:")
    for lag, (r, n) in top:
        print(f"    {lag:3d}h: r={r:+.3f} (n={n})")
    return top[0]

def main():
    por_est = load()
    orleans = por_est.get('84249998', [])
    pouso = por_est.get('84580000', [])
    
    print("="*70)
    print("TESTE DIFERENCIADO — REMOVENDO TENDENCIA")
    print("="*70)
    
    # SERIE ABSOLUTA (baseline — ja fizemos)
    chuva_abs = serie_horaria(orleans, 'chuva', 'soma')
    vazao_abs = serie_horaria(pouso, 'vazao', 'media')
    
    print("\n--- BASELINE: serie absoluta (com tendencia) ---")
    testar_lag(chuva_abs, vazao_abs, 48, "chuva abs vs vazao abs")
    
    # SERIE DIFERENCIADA (remove tendencia)
    print("\n\n--- TESTE REAL: serie diferenciada (sem tendencia) ---")
    chuva_abs2 = serie_horaria(orleans, 'chuva', 'soma')
    vazao_abs2 = serie_horaria(pouso, 'vazao', 'media')
    vazao_delta = diferenciar(vazao_abs2)
    
    testar_lag(chuva_abs2, vazao_delta, 48, "chuva abs vs vazao DELTA")
    
    # SERIE DIFERENCIADA DUPLA
    print("\n\n--- TESTE 2: chuva delta vs vazao delta ---")
    chuva_delta = diferenciar(chuva_abs2)
    testar_lag(chuva_delta, vazao_delta, 48, "chuva DELTA vs vazao DELTA")
    
    print("\n\n" + "="*70)
    print("INTERPRETACAO:")
    print("="*70)
    print("""
  - Se lag forte persistir nas 3 series: sinal real
  - Se cair/sumir na serie diferenciada: artefato de tendencia
  - Se so aparecer na DELTA vs DELTA: sinal fraco mas real
    """)

if __name__ == "__main__":
    main()
