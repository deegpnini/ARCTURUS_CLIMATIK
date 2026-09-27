#!/usr/bin/env python3
"""
Detector de eventos hidrologicos V2 — baseado em hidrograma.
Nao usa gap_min. Usa recessao + analise de picos.
"""
import csv, os
from datetime import datetime, timedelta
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def detectar_eventos_v2(rows, p95, p75):
    """
    Detector hidrologico:
    1. Entra em evento quando cota > p95
    2. Permanece enquanto recessao nao cair abaixo de p75
    3. Multiplos picos sao analisados
    """
    eventos = []
    ev = None
    ultima_abaixo_p95 = None
    leituras_ev = []

    for r in rows:
        v = r.get('cota', '')
        if not v: continue
        try: cota = float(v)
        except: continue
        try: dt = datetime.strptime(r['timestamp'], "%Y-%m-%d %H:%M:%S")
        except: continue

        if cota > p95:
            # Dentro de evento
            if ev is None:
                ev = {
                    'inicio': dt,
                    'fim': dt,
                    'pico': cota,
                    'pico_dt': dt,
                    'leituras': 1,
                    'minimo_pos_pico': cota,
                    'picos': [{'dt': dt, 'valor': cota}],
                }
            else:
                ev['fim'] = dt
                ev['leituras'] += 1
                if cota > ev['pico']:
                    ev['pico'] = cota
                    ev['pico_dt'] = dt
                # Detecta pico local (sobe e desce)
                if ev['leituras'] > 1:
                    prev = leituras_ev[-1] if leituras_ev else None
                    if prev and prev['cota'] > cota and prev['cota'] > 0:
                        # Foi pico e agora ta descendo
                        ev['picos'].append({'dt': prev['dt'], 'valor': prev['cota']})
                # Atualiza minimo pos-pico
                if cota < ev['minimo_pos_pico']:
                    ev['minimo_pos_pico'] = cota
            leituras_ev.append({'dt': dt, 'cota': cota})
            ultima_abaixo_p95 = None

        else:
            # Abaixo do p95
            if ev is not None:
                # Ainda dentro do evento?
                # Regra: permanece se nao caiu abaixo de p75 E nao passou muito tempo
                if cota < p75:
                    # Recessao profunda: finaliza evento
                    eventos.append(ev)
                    ev = None
                    leituras_ev = []
                else:
                    # Recessao superficial: mantem evento aberto
                    ev['fim'] = dt
                    ev['leituras'] += 1
                    leituras_ev.append({'dt': dt, 'cota': cota})
            ultima_abaixo_p95 = dt

    if ev is not None:
        eventos.append(ev)

    return eventos

def analisar_multiplos_picos(eventos):
    """Analisa se eventos com multiplos picos devem ser separados."""
    for ev in eventos:
        picos = ev.get('picos', [])
        if len(picos) < 2:
            continue
        # Ordena picos por tempo
        picos = sorted(picos, key=lambda x: x['dt'])
        ev['picos'] = picos
        # Calcula vales entre picos
        vales = []
        for i in range(1, len(picos)):
            # Encontra minimo entre pico[i-1] e pico[i]
            dt1 = picos[i-1]['dt']
            dt2 = picos[i]['dt']
            vale_min = min(picos[i-1]['valor'], picos[i]['valor'])
            # (simplificado: usa o menor dos dois picos como proxy)
            vales.append({
                'de': picos[i-1],
                'para': picos[i],
                'min_proxy': vale_min,
            })
        ev['vales'] = vales

def main():
    arquivo = f"{CACHE}/dataset_1h.csv"
    rows = list(csv.DictReader(open(arquivo)))

    # P95 e P75
    cotas = [float(r['cota']) for r in rows if r.get('cota')]
    cotas.sort()
    p75 = cotas[int(len(cotas)*0.75)]
    p95 = cotas[int(len(cotas)*0.95)]

    print(f"P75: {p75:.2f}")
    print(f"P95: {p95:.2f}")
    print()

    eventos = detectar_eventos_v2(rows, p95, p75)
    analisar_multiplos_picos(eventos)

    print("="*70)
    print(f"EVENTOS V2: {len(eventos)}")
    print("="*70)
    print()

    # Distribuicao por ano
    por_ano = defaultdict(int)
    for e in eventos:
        por_ano[e['inicio'].year] += 1
    print(f"Por ano: {dict(sorted(por_ano.items()))}")
    print()

    # Top 20 maiores
    print("TOP 20 eventos (por pico):")
    for e in sorted(eventos, key=lambda x: -x['pico'])[:20]:
        duracao = (e['fim'] - e['inicio']).total_seconds() / 3600
        n_picos = len(e.get('picos', []))
        print(f"  {e['inicio'].strftime('%Y-%m-%d %H:%M')} -> {e['fim'].strftime('%Y-%m-%d %H:%M')}")
        print(f"    duracao: {duracao:.1f}h | pico: {e['pico']:.1f} | leituras: {e['leituras']} | picos: {n_picos}")

if __name__ == "__main__":
    main()
