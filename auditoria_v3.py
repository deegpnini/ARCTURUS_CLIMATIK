#!/usr/bin/env python3
"""
Auditoria V3 dos 28 episodios candidatos.
Analisa picos + vales + independencia hidrologica.
SEPARA o evento de 21/09 como teste OPERACIONAL.
"""
import csv, json
from datetime import datetime, timedelta

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
                ev = {'inicio': dt, 'fim': dt, 'pico': cota,
                      'leituras': 1, 'idx_ini': None, 'idx_fim': None}
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

def analisar_vales(valores, idx_ini, idx_fim):
    """Analisa vales dentro do evento (proxy para independencia)."""
    if idx_ini is None or idx_fim is None:
        return None
    # Encontra picos e vales locais no intervalo
    picos = []
    vales = []
    for i in range(idx_ini + 1, idx_fim):
        if i <= 0 or i >= len(valores) - 1: continue
        if valores[i] is None: continue
        if valores[i-1] is None or valores[i+1] is None: continue
        if valores[i] > valores[i-1] and valores[i] > valores[i+1]:
            picos.append({'idx': i, 'valor': valores[i]})
        elif valores[i] < valores[i-1] and valores[i] < valores[i+1]:
            vales.append({'idx': i, 'valor': valores[i]})
    return picos, vales

def main():
    arquivo = f"{CACHE}/dataset_1h.csv"
    rows = list(csv.DictReader(open(arquivo)))
    valores = [float(r['cota']) if r.get('cota') else None for r in rows]
    timestamps = [r['timestamp'] for r in rows]

    cotas = sorted([v for v in valores if v is not None])
    p75 = cotas[int(len(cotas)*0.75)]
    p95 = cotas[int(len(cotas)*0.95)]

    # Indexa
    ts_to_idx = {ts: i for i, ts in enumerate(timestamps)}

    eventos = detectar_eventos_v2(rows, p95, p75)

    # Preenche idx
    for ev in eventos:
        ev['idx_ini'] = ts_to_idx.get(ev['inicio'].strftime("%Y-%m-%d %H:%M:%S"))
        ev['idx_fim'] = ts_to_idx.get(ev['fim'].strftime("%Y-%m-%d %H:%M:%S"))

    print("="*110)
    print(f"AUDITORIA V3 — {len(eventos)} EPISODIOS CANDIDATOS (P95 > {p95:.1f} cm)")
    print("="*110)
    print()
    print(f"{'#':3s} | {'Inicio':16s} | {'Dur':6s} | {'Pico':6s} | {'#Picos':7s} | {'#Vales':7s} | {'Multipico':10s} | {'Independ.':10s}")
    print("-"*110)

    def e_multipico(n_picos):
        return "SIM" if n_picos >= 3 else "nao"

    def grau_independencia(picos, vales):
        if len(picos) < 2:
            return "unico"
        # Media da profundidade dos vales entre picos
        profundidades = []
        for v in vales:
            # Encontra picos vizinhos
            v_esq = [p for p in picos if p['idx'] < v['idx']]
            v_dir = [p for p in picos if p['idx'] > v['idx']]
            if v_esq and v_dir:
                p_esq = v_esq[-1]['valor']
                p_dir = v_dir[0]['valor']
                p_menor = min(p_esq, p_dir)
                profundidade = (p_menor - v['valor']) / p_menor if p_menor > 0 else 0
                profundidades.append(profundidade)
        if not profundidades:
            return "n/a"
        media = sum(profundidades) / len(profundidades)
        if media < 0.10: return "baixa"
        if media < 0.25: return "media"
        return "alta"

    eventos_info = []
    for i, ev in enumerate(eventos, 1):
        analise = analisar_vales(valores, ev['idx_ini'], ev['idx_fim'])
        if analise:
            picos, vales = analise
        else:
            picos, vales = [], []

        dur = (ev['fim'] - ev['inicio']).total_seconds() / 3600
        mult = e_multipico(len(picos))
        ind = grau_independencia(picos, vales)

        print(f"{i:3d} | {ev['inicio'].strftime('%Y-%m-%d %H:%M'):16s} | {dur:5.1f}h | "
              f"{ev['pico']:6.1f} | {len(picos):7d} | {len(vales):7d} | {mult:10s} | {ind:10s}")

        eventos_info.append({
            'n': i,
            'inicio': ev['inicio'].isoformat(),
            'fim': ev['fim'].isoformat(),
            'duracao_h': dur,
            'pico': ev['pico'],
            'n_picos': len(picos),
            'n_vales': len(vales),
            'multipico': mult,
            'independencia': ind,
        })

    # Salva
    out = f"{CACHE}/auditoria_v3.json"
    with open(out, 'w') as f:
        json.dump({'p95': p95, 'p75': p75, 'eventos': eventos_info}, f, indent=2, default=str)
    print()
    print(f"Salvo: {out}")

    # ============================================================
    # SEPARACAO DO EVENTO 21/09/2026 (teste OPERACIONAL)
    # ============================================================
    print()
    print("="*110)
    print("SEPARACAO — TESTE OPERACIONAL vs HISTORICO")
    print("="*110)

    historicos = []
    operacionais = []
    for ev in eventos_info:
        if ev['inicio'].startswith('2026-09-21'):
            operacionais.append(ev)
        else:
            historicos.append(ev)

    print(f"\nEventos historicos (ja fechados): {len(historicos)}")
    print(f"Eventos operacionais (ainda em curso): {len(operacionais)}")

    # Proposta de split sobre historicos
    n = len(historicos)
    n_tr = int(n * 0.70)
    n_va = int(n * 0.15)

    print(f"\nSplit proposto sobre historicos:")
    print(f"  Treino:     {n_tr} eventos")
    print(f"  Validacao:  {n_va} eventos")
    print(f"  Teste:      {n - n_tr - n_va} eventos")

    if historicos:
        print(f"\n  Treino:    {historicos[0]['inicio'][:10]} a {historicos[n_tr-1]['fim'][:10]}")
        print(f"  Validacao: {historicos[n_tr]['inicio'][:10]} a {historicos[n_tr+n_va-1]['fim'][:10]}")
        print(f"  Teste:     {historicos[n_tr+n_va]['inicio'][:10]} a {historicos[-1]['fim'][:10]}")

    # Salva split final
    split = {
        'historico': historicos,
        'operacional': operacionais,
        'treino_idx': list(range(0, n_tr)),
        'val_idx': list(range(n_tr, n_tr + n_va)),
        'teste_idx': list(range(n_tr + n_va, n)),
    }
    with open(f"{CACHE}/split_v3.json", 'w') as f:
        json.dump(split, f, indent=2, default=str)
    print(f"\nSalvo: {CACHE}/split_v3.json")

if __name__ == "__main__":
    main()
