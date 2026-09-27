#!/usr/bin/env python3
"""
Analise hidrologica da cadeia Tubarao - ANA
Le o arquivo ana_cadeia_tubarao_7d.json

v2 - corrigido:
  - zero real != ausente (usa is not None)
  - suporta virgula decimal
  - correlacao cruzada com lag (Orleans -> Rio do Pouso)
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def parse_dt(s):
    if not s: return None
    try:
        return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
    except:
        return None

def parse_num(s):
    """Converte string numerica pra float, tratando virgula e zero real."""
    if s is None: return None
    if isinstance(s, (int, float)): return float(s)
    s = str(s).strip()
    if not s: return None
    s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return None

def load():
    d = json.load(open(f"{CACHE}/ana_cadeia_tubarao_7d.json"))
    items = d.get('items', [])
    
    por_est = defaultdict(list)
    for it in items:
        cod = it.get('codigoestacao')
        dt = parse_dt(it.get('Data_Hora_Medicao'))
        if not dt: continue
        por_est[cod].append({
            'dt': dt,
            'chuva': parse_num(it.get('Chuva_Adotada')),
            'cota': parse_num(it.get('Cota_Adotada')),
            'vazao': parse_num(it.get('Vazao_Adotada')),
        })
    
    for cod in por_est:
        por_est[cod].sort(key=lambda x: x['dt'])
    
    return por_est

def resumo_estacao(cod, leituras):
    if not leituras:
        return
    print(f"\n{'='*70}")
    print(f"ESTACAO {cod}")
    print(f"{'='*70}")
    print(f"Leituras: {len(leituras)}")
    print(f"Periodo: {leituras[0]['dt']} a {leituras[-1]['dt']}")
    
    chuvas = [l['chuva'] for l in leituras if l['chuva'] is not None]
    cotas = [l['cota'] for l in leituras if l['cota'] is not None]
    vazoes = [l['vazao'] for l in leituras if l['vazao'] is not None]
    
    if chuvas:
        print(f"\nCHUVA (mm):")
        print(f"  leituras: {len(chuvas)}")
        print(f"  total: {sum(chuvas):.2f} mm")
        print(f"  max: {max(chuvas):.2f} mm")
        print(f"  nao-zero: {sum(1 for c in chuvas if c > 0)}")
    
    if cotas:
        print(f"\nCOTA:")
        print(f"  leituras: {len(cotas)}")
        print(f"  min: {min(cotas):.2f}")
        print(f"  max: {max(cotas):.2f}")
        print(f"  amplitude: {max(cotas)-min(cotas):.2f}")
    
    if vazoes:
        print(f"\nVAZAO (m3/s):")
        print(f"  leituras: {len(vazoes)}")
        print(f"  min: {min(vazoes):.2f}")
        print(f"  max: {max(vazoes):.2f}")
        print(f"  amplitude: {max(vazoes)-min(vazoes):.2f}")
        if min(vazoes) > 0:
            print(f"  variacao: {max(vazoes)/min(vazoes):.2f}x")
        
        v_max = max(vazoes)
        v_min = min(vazoes)
        idx_max = next(i for i, l in enumerate(leituras) if l['vazao'] == v_max)
        idx_min = next(i for i, l in enumerate(leituras) if l['vazao'] == v_min)
        print(f"\n  Pico: {leituras[idx_max]['dt']}")
        print(f"  Vale: {leituras[idx_min]['dt']}")
        if idx_max > idx_min:
            delta = leituras[idx_max]['dt'] - leituras[idx_min]['dt']
            horas = max(delta.total_seconds()/3600, 1)
            print(f"  Subida em: {delta}")
            print(f"  Taxa: {(v_max-v_min)/horas:.3f} m3/s por hora")

def correlacao_com_lag(orleans, pouso, max_lag_horas=48):
    """
    Testa cada lag e ve qual maximiza correlacao
    chuva em Orleans <-> vazao em Rio do Pouso.
    """
    import statistics
    
    def para_serie_horaria(leituras, campo):
        buckets = defaultdict(list)
        for l in leituras:
            if l[campo] is not None:
                hora = l['dt'].replace(minute=0, second=0, microsecond=0)
                buckets[hora].append(l[campo])
        return {h: sum(v)/len(v) for h, v in buckets.items()}
    
    chuva_orleans = para_serie_horaria(orleans, 'chuva')
    vazao_pouso = para_serie_horaria(pouso, 'vazao')
    
    print(f"  Orleans: {len(chuva_orleans)} horas com chuva")
    print(f"  Rio do Pouso: {len(vazao_pouso)} horas com vazao")
    
    if len(chuva_orleans) < 5 or len(vazao_pouso) < 5:
        print("  !! Dados insuficientes (minimo 5 horas de cada)")
        return None
    
    horas_comuns = sorted(set(chuva_orleans) | set(vazao_pouso))
    resultados = {}
    
    for lag in range(0, max_lag_horas + 1):
        pares = []
        for h in horas_comuns:
            h_efeito = h + timedelta(hours=lag)
            if h in chuva_orleans and h_efeito in vazao_pouso:
                pares.append((chuva_orleans[h], vazao_pouso[h_efeito]))
        
        if len(pares) >= 5:
            xs = [p[0] for p in pares]
            ys = [p[1] for p in pares]
            if len(set(xs)) < 2 or len(set(ys)) < 2:
                continue
            try:
                r = statistics.correlation(xs, ys)
                resultados[lag] = (r, len(pares))
            except statistics.StatisticsError:
                continue
    
    if not resultados:
        print("  !! Nao foi possivel calcular (poucos pares sobrepostos)")
        print("  (esperado com so 7 dias de dado)")
        return None
    
    print(f"\n  Top 5 lags (por correlacao):")
    top = sorted(resultados.items(), key=lambda x: -abs(x[1][0]))[:5]
    for lag, (r, n) in top:
        print(f"    {lag:3d}h: r={r:+.3f} (n={n})")
    
    melhor = top[0]
    print(f"\n  MELHOR: lag={melhor[0]}h, r={melhor[1][0]:+.3f}")
    print(f"  INTERPRETACAO: chuva em Orleans leva ~{melhor[0]}h")
    print(f"                 pra afetar vazao em Rio do Pouso")
    print(f"  AVISO: com 7 dias de dado, e' ESTIMATIVA EXPLORATORIA")
    print(f"         (validar com mais historico + eventos severos)")
    return melhor[0]

def main():
    por_est = load()
    print("ANALISE HIDROLOGICA — CADEIA RIO TUBARAO")
    print(f"Total de estacoes: {len(por_est)}")
    
    for cod in sorted(por_est.keys()):
        resumo_estacao(cod, por_est[cod])
    
    print(f"\n{'='*70}")
    print("ANALISE CRUZADA: ORLEANS -> RIO DO POUSO")
    print(f"{'='*70}")
    
    orleans = por_est.get('84249998', [])
    pouso = por_est.get('84580000', [])
    
    if not orleans or not pouso:
        print("!! Dados insuficientes")
        return
    
    print(f"\nCalculando defasagem real (correlacao cruzada):")
    correlacao_com_lag(orleans, pouso, max_lag_horas=48)

if __name__ == "__main__":
    main()
