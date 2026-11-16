#!/usr/bin/env python3
"""
Detecta EVENTOS distintos (episodios de cheia).
Um evento = bloco de leituras consecutivas acima do limiar.
Separa por retorno ao normal.
"""
import csv, os
from datetime import datetime, timedelta
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def detectar_eventos(arquivo, limiar, gap_min=120):
    """
    Detecta eventos acima do limiar.
    gap_min: leituras abaixo do limiar por mais de X min quebram evento.
    """
    with open(arquivo) as f:
        rows = list(csv.DictReader(f))

    # Pega coluna do target (cota atual = cota(t))
    eventos = []
    evento_atual = None
    ultima_data = None

    for r in rows:
        cota_str = r.get('cota', '')
        if not cota_str: continue
        try:
            cota = float(cota_str)
        except:
            continue
        try:
            dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
        except:
            continue

        if cota > limiar:
            if evento_atual is None:
                # Comeca evento
                evento_atual = {
                    'inicio': dt,
                    'fim': dt,
                    'leituras': 1,
                    'cota_max': cota,
                    'cota_inicio': cota,
                }
            else:
                # Verifica gap
                if ultima_data and (dt - ultima_data).total_seconds() / 60 > gap_min:
                    # Quebra evento (voltou ao normal)
                    eventos.append(evento_atual)
                    evento_atual = {
                        'inicio': dt,
                        'fim': dt,
                        'leituras': 1,
                        'cota_max': cota,
                        'cota_inicio': cota,
                    }
                else:
                    evento_atual['fim'] = dt
                    evento_atual['leituras'] += 1
                    evento_atual['cota_max'] = max(evento_atual['cota_max'], cota)
            ultima_data = dt
        else:
            # Cota abaixo do limiar
            if evento_atual is not None:
                eventos.append(evento_atual)
                evento_atual = None
            ultima_data = dt

    if evento_atual is not None:
        eventos.append(evento_atual)

    return eventos

def main():
    # Usa dataset_1h (cota atual e target)
    arquivo = f"{CACHE}/dataset_1h.csv"

    # Vamos usar cota (nao target) para identificar eventos
    # e o target_1h ja foi construido

    # Calcular limiares baseado nos targets do dataset
    with open(arquivo) as f:
        rows = list(csv.DictReader(f))

    valores = []
    for r in rows:
        t = r.get('target_1h', '')
        if t:
            try: valores.append(float(t))
            except: pass

    valores.sort()
    def pct(p):
        idx = int(len(valores) * p)
        return valores[min(idx, len(valores)-1)]

    p90 = pct(0.90)
    p95 = pct(0.95)
    p99 = pct(0.99)

    print(f"Limiares (target_1h):")
    print(f"  P90: {p90:.2f}")
    print(f"  P95: {p95:.2f}")
    print(f"  P99: {p99:.2f}")
    print()

    for nome, limiar in [('P90', p90), ('P95', p95), ('P99', p99)]:
        eventos = detectar_eventos(arquivo, limiar)
        print(f"=== Limiar {nome} ({limiar:.2f}) ===")
        print(f"Eventos distintos: {len(eventos)}")
        if eventos:
            duracoes = [(e['fim'] - e['inicio']).total_seconds() / 3600 for e in eventos]
            print(f"  Duracao media: {sum(duracoes)/len(duracoes):.1f}h")
            print(f"  Duracao max: {max(duracoes):.1f}h")
            print(f"  Total leituras em eventos: {sum(e['leituras'] for e in eventos)}")
            print(f"  Top 5 maiores:")
            for e in sorted(eventos, key=lambda x: -x['leituras'])[:5]:
                dur = (e['fim'] - e['inicio']).total_seconds() / 3600
                print(f"    {e['inicio']} -> {e['fim']}  ({dur:.1f}h, {e['leituras']} leituras, pico {e['cota_max']:.1f})")
        print()

if __name__ == "__main__":
    main()
