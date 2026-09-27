#!/usr/bin/env python3
"""
Auditoria Itajai-Acu + Ararangua.
Sem treinar, sem imputar. So evidencia.
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

# Candidatas - as duas bacias
CANDIDATAS = {
    'ITAJAI_ACU': [
        ('83300200', 'RIO DO SUL - NOVO', 'Itajai-Acu'),
        ('83105000', 'SALTINHO', 'Itajai do Sul'),
        ('83050000', 'TAIO', 'Itajai do Oeste'),
        ('83690000', 'INDAIAL', 'Itajai-Acu'),
        ('83840000', 'GASPAR', 'Itajai-Acu'),
        ('83800002', 'BLUMENAU (PCD)', 'Itajai-Acu'),
        ('84017010', 'BLUMENAU', 'Itajai-Acu'),
        ('83870001', 'ILHOTA-JUSANTE', 'Itajai-Acu'),
        ('83905000', 'BRUSQUE', 'Itajai-Mirim'),
    ],
    'ARARANGUA': [
        ('84949800', 'ERMO', 'Itoupava'),
        ('84820000', 'FORQUILHINHA', 'Mae Luzia'),
        ('84820002', 'FORQUILHINHA', 'Mae Luzia'),
        ('84850500', 'MELEIRO', 'Manuel Alves'),
        ('84853000', 'FOZ DO MANUEL ALVES', 'Manuel Alves'),
        ('84853001', 'FOZ DO MANUEL ALVES', 'Manuel Alves'),
        ('84949000', 'TURVO', 'Amola Faca'),
        ('84802000', 'AR28 - NOVA VENEZA', 'Ararangua'),
        ('84835000', 'AR76 - CRICIUMA', 'Ararangua'),
        ('84840000', 'AR85 - MARACAJA', 'Ararangua'),
        ('84845000', 'AR86 - MARACAJA', 'Ararangua'),
    ],
}

def get_json(url, token, timeout=60):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def auditar(token, codigo, meses=12):
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
        except:
            continue
        todas.extend(d.get('items', []) if d else [])

    vistos = set()
    unicos = []
    def p(s):
        try: return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except: return None

    for it in todas:
        ts = it.get('Data_Hora_Medicao', '')
        if ts and ts not in vistos and p(ts):
            vistos.add(ts)
            unicos.append(it)
    unicos.sort(key=lambda x: p(x.get('Data_Hora_Medicao', '')))

    if not unicos:
        return None

    total = len(unicos)
    com_cota = 0
    cotas = []
    gaps = 0
    maior_gap = 0

    for i, it in enumerate(unicos):
        c = it.get('Cota_Adotada')
        if c and c not in ('', '0.00'):
            try:
                v = float(str(c).replace(',', '.'))
                com_cota += 1
                cotas.append(v)
            except: pass
        if i > 0:
            t1 = p(unicos[i-1]['Data_Hora_Medicao'])
            t2 = p(it['Data_Hora_Medicao'])
            if t1 and t2:
                d = (t2 - t1).total_seconds() / 3600
                if d > 0.5:
                    gaps += 1
                    if d > maior_gap:
                        maior_gap = d

    meses_cob = defaultdict(int)
    for it in unicos:
        meses_cob[it['Data_Hora_Medicao'][:7]] += 1

    return {
        'total': total,
        'com_cota': com_cota,
        'pct_cota': com_cota/total*100 if total else 0,
        'gaps': gaps,
        'pct_gaps': gaps/total*100 if total else 0,
        'maior_gap_h': maior_gap,
        'primeiro': unicos[0]['Data_Hora_Medicao'][:19],
        'ultimo': unicos[-1]['Data_Hora_Medicao'][:19],
        'cota_min': min(cotas) if cotas else None,
        'cota_max': max(cotas) if cotas else None,
        'meses': len(meses_cob),
    }

def main():
    token = get_token()
    print(f"Token: {len(token)} chars\n")

    for bacia, lista in CANDIDATAS.items():
        print(f"\n{'='*90}")
        print(f"BACIA: {bacia}")
        print(f"{'='*90}")
        print(f"\n{'Codigo':12s} | {'Nome':30s} | {'Total':7s} | {'Cota%':6s} | {'Gaps':5s} | {'MaxGap':7s} | {'Periodo'}")
        print("-"*120)

        for codigo, nome, rio in lista:
            try:
                r = auditar(token, codigo, meses=12)
            except Exception as e:
                print(f"{codigo:12s} | {nome[:30]:30s} | ERRO: {e}")
                continue
            if r is None:
                print(f"{codigo:12s} | {nome[:30]:30s} | SEM DADOS")
                continue
            print(f"{codigo:12s} | {nome[:30]:30s} | {r['total']:7d} | {r['pct_cota']:5.1f}% | {r['gaps']:5d} | {r['maior_gap_h']:6.1f}h | {r['primeiro'][:10]} a {r['ultimo'][:10]}")

if __name__ == "__main__":
    main()
