#!/usr/bin/env python3
"""
V2: corrige ordenacao e contagem de gaps.
Audita 3 meses de cada candidata principal.
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
INV = f"{CACHE}/ana_inventario_sc.json"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

# Estacoes ANCORA por bacia (as melhores, escolhidas manualmente)
ANCORAS = {
    'ITAJAI_ACU': [
        ('83300200', 'RIO DO SUL - NOVO'),
        ('83800002', 'BLUMENAU (PCD)'),
        ('83900000', 'BRUSQUE (PCD)'),
    ],
    'ARARANGUA': [
        ('84820000', 'FORQUILINHA'),
        ('84949800', 'ERMO'),
    ],
    'CHAPECO': [
        ('73900000', 'SAUDADES'),
        ('73770000', 'PORTO FAE NOVO'),
    ],
    'URUGUAI': [
        ('74329000', 'ITAPIRANGA'),
        ('74050000', 'UHE FOZ DO CHAPECO JUSANTE'),
    ],
    'TUBARAO': [
        ('84580000', 'RIO DO POUSO'),
    ],
}

def get_json(url, token, timeout=60):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def auditar(token, codigo, meses=3):
    """Puxa serie dos ultimos N meses. Corrigido."""
    hoje = datetime.now()
    todas = []

    for i in range(meses):
        data_ref = hoje - timedelta(days=30 * (i + 1))
        url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
               f"?Codigos_Estacoes={codigo}"
               f"&Tipo%20Filtro%20Data=DATA_LEITURA"
               f"&Range%20Intervalo%20de%20busca=DIAS_30"
               f"&Data%20de%20Busca%20(yyyy-MM-dd)={data_ref.strftime('%Y-%m-%d')}")
        try:
            d = get_json(url, token)
        except Exception as e:
            continue
        items = d.get('items', []) if d else []
        todas.extend(items)

    # Deduplica por timestamp
    vistos = set()
    unicos = []
    for it in todas:
        ts = it.get('Data_Hora_Medicao', '')
        if ts and ts not in vistos:
            vistos.add(ts)
            unicos.append(it)

    # Ordena UMA VEZ no final
    def parse_ts(s):
        try:
            return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except:
            return None

    unicos = [x for x in unicos if parse_ts(x.get('Data_Hora_Medicao', ''))]
    unicos.sort(key=lambda x: parse_ts(x.get('Data_Hora_Medicao', '')))

    if not unicos:
        return None

    # Metricas
    total = len(unicos)
    com_cota = 0
    cotas = []
    gaps_grandes = 0

    for i, it in enumerate(unicos):
        c = it.get('Cota_Adotada')
        if c and c not in ('', '0.00'):
            try:
                v = float(str(c).replace(',', '.'))
                com_cota += 1
                cotas.append(v)
            except:
                pass
        # Gap
        if i > 0:
            t1 = parse_ts(unicos[i-1]['Data_Hora_Medicao'])
            t2 = parse_ts(it['Data_Hora_Medicao'])
            if t1 and t2 and (t2 - t1).total_seconds() > 1800:
                gaps_grandes += 1

    return {
        'total': total,
        'com_cota': com_cota,
        'pct_cota': com_cota / total * 100 if total else 0,
        'gaps_grandes': gaps_grandes,
        'pct_gaps': gaps_grandes / total * 100 if total else 0,
        'primeiro': unicos[0]['Data_Hora_Medicao'][:19],
        'ultimo': unicos[-1]['Data_Hora_Medicao'][:19],
        'cota_min': min(cotas) if cotas else None,
        'cota_max': max(cotas) if cotas else None,
    }

def main():
    token = get_token()
    print(f"Token: {len(token)} chars\n")

    for bacia, estacoes in ANCORAS.items():
        print(f"\n{'='*80}")
        print(f"BACIA: {bacia}")
        print(f"{'='*80}")
        for codigo, nome in estacoes:
            print(f"\n  {codigo} — {nome}")
            try:
                r = auditar(token, codigo, meses=3)
            except Exception as e:
                print(f"    ERRO: {e}")
                continue
            if r is None:
                print(f"    SEM DADOS")
                continue
            print(f"    Total: {r['total']} leituras")
            print(f"    Com cota: {r['com_cota']} ({r['pct_cota']:.1f}%)")
            print(f"    Gaps >30min: {r['gaps_grandes']} ({r['pct_gaps']:.1f}%)")
            print(f"    Periodo: {r['primeiro']} a {r['ultimo']}")
            if r['cota_min'] is not None:
                print(f"    Cota: {r['cota_min']:.1f} a {r['cota_max']:.1f} cm")

if __name__ == "__main__":
    main()
