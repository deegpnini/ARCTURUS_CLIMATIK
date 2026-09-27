#!/usr/bin/env python3
"""
Auditoria de picos do detector V2.
Suaviza hidrograma e re-detecta picos com prominence minima.
"""
import csv, os
from datetime import datetime, timedelta
from collections import defaultdict

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"

def suavizar(valores, janela=3):
    """Media movel centralizada (janela=3 -> 45 min).
    Preserva picos mais longos que 45 min."""
    n = len(valores)
    out = []
    for i in range(n):
        ini = max(0, i - janela // 2)
        fim = min(n, i + janela // 2 + 1)
        v = [valores[j] for j in range(ini, fim) if valores[j] is not None]
        if v:
            out.append(sum(v) / len(v))
        else:
            out.append(None)
    return out

def detectar_picos(valores, prominence=20.0, distancia_min=4):
    """
    Detecta picos locais com:
    - prominence minima (diferenca em relacao ao vale)
    - distancia minima entre picos (4 leituras = 1h)
    """
    n = len(valores)
    picos = []
    i = 1
    while i < n - 1:
        if valores[i] is None:
            i += 1; continue
        # Verifica se eh maximo local (janela de 3)
        if valores[i-1] is not None and valores[i+1] is not None:
            if valores[i] >= valores[i-1] and valores[i] >= valores[i+1]:
                # Calcula prominence
                # Sobe para esquerda ate passar por cota menor
                j = i - 1
                min_esq = valores[i]
                while j >= 0 and valores[j] is not None:
                    if valores[j] < min_esq:
                        min_esq = valores[j]
                    if valores[j] > valores[i]:
                        break
                    j -= 1
                # Sobe para direita
                k = i + 1
                min_dir = valores[i]
                while k < n and valores[k] is not None:
                    if valores[k] < min_dir:
                        min_dir = valores[k]
                    if valores[k] > valores[i]:
                        break
                    k += 1
                prominencia = valores[i] - max(min_esq, min_dir)
                if prominencia >= prominence:
                    picos.append({
                        'idx': i,
                        'valor': valores[i],
                        'prominencia': prominencia,
                    })
                    i += distancia_min
                    continue
        i += 1
    return picos

def detectar_eventos_v2(rows, p95, p75):
    """Mesmo detector V2 original."""
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
                ev = {'inicio': dt, 'fim': dt, 'pico': cota,
                      'leituras': 1, 'idx_inicio': len(eventos)}
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

    cotas = [float(r['cota']) for r in rows if r.get('cota')]
    cotas.sort()
    p75 = cotas[int(len(cotas)*0.75)]
    p95 = cotas[int(len(cotas)*0.95)]

    # Extrai valores de cota como array
    valores = [float(r['cota']) for r in rows if r.get('cota')]
    timestamps = [r['timestamp'] for r in rows if r.get('cota')]

    print("="*70)
    print("AUDITORIA DE PICOS")
    print("="*70)
    print(f"P75: {p75:.2f} | P95: {p95:.2f}")
    print(f"Total de leituras: {len(valores)}")
    print()

    # SEM suavizacao
    picos_brutos = detectar_picos(valores, prominence=20.0, distancia_min=4)
    print(f"Picos (sem suavizacao): {len(picos_brutos)}")

    # COM suavizacao (janela 3 = 45 min)
    valores_suave = suavizar(valores, janela=3)
    picos_suave = detectar_picos(valores_suave, prominence=20.0, distancia_min=4)
    print(f"Picos (suavizado 45min): {len(picos_suave)}")

    # COM suavizacao (janela 5 = 75 min)
    valores_suave5 = suavizar(valores, janela=5)
    picos_suave5 = detectar_picos(valores_suave5, prominence=20.0, distancia_min=4)
    print(f"Picos (suavizado 75min): {len(picos_suave5)}")

    # Eventos V2
    eventos = detectar_eventos_v2(rows, p95, p75)
    print(f"\nEventos V2: {len(eventos)}")
    print()

    # TOP 10 eventos com contagem de picos
    print("="*70)
    print("TOP 10 EVENTOS — PICOS POR DETECTOR")
    print("="*70)
    print(f"{'Inicio':20s} | {'Pico':6s} | {'Picos_brutos':13s} | {'Suave45':8s} | {'Suave75':8s}")
    print("-"*70)

    for ev in sorted(eventos, key=lambda x: -x['pico'])[:10]:
        # Encontra idx do inicio e fim
        try:
            idx_ini = timestamps.index(ev['inicio'].strftime("%Y-%m-%d %H:%M:%S"))
            idx_fim = timestamps.index(ev['fim'].strftime("%Y-%m-%d %H:%M:%S"))
        except ValueError:
            continue

        # Conta picos nesse intervalo
        p_b = sum(1 for p in picos_brutos if idx_ini <= p['idx'] <= idx_fim)
        p_s3 = sum(1 for p in picos_suave if idx_ini <= p['idx'] <= idx_fim)
        p_s5 = sum(1 for p in picos_suave5 if idx_ini <= p['idx'] <= idx_fim)

        print(f"{ev['inicio'].strftime('%Y-%m-%d %H:%M'):20s} | {ev['pico']:6.1f} | {p_b:13d} | {p_s3:8d} | {p_s5:8d}")

if __name__ == "__main__":
    main()
