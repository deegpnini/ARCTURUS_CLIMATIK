#!/usr/bin/env python3
"""
Auditoria completa das 3 ancoras.
Puxa historico desde 2024 (ou quando comecou).
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

ANCORAS = {
    'CHAPECO': ('73770000', 'PORTO FAE NOVO'),
    'URUGUAI': ('74329000', 'ITAPIRANGA'),
    'TUBARAO': ('84580000', 'RIO DO POUSO'),
}

def get_json(url, token, timeout=60):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def auditar_completo(token, codigo, meses=12):
    hoje = datetime.now()
    todos = []

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
        todos.extend(d.get('items', []) if d else [])

    # Deduplica + ordena
    vistos = set()
    unicos = []
    def parse_ts(s):
        try: return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except: return None

    for it in todos:
        ts = it.get('Data_Hora_Medicao', '')
        if ts and ts not in vistos and parse_ts(ts):
            vistos.add(ts)
            unicos.append(it)
    unicos.sort(key=lambda x: parse_ts(x.get('Data_Hora_Medicao', '')))

    if not unicos:
        return None

    # Metricas
    total = len(unicos)
    com_cota = 0
    cotas = []
    gaps = 0

    for i, it in enumerate(unicos):
        c = it.get('Cota_Adotada')
        if c and c not in ('', '0.00'):
            try:
                v = float(str(c).replace(',', '.'))
                com_cota += 1
                cotas.append(v)
            except: pass
        if i > 0:
            t1 = parse_ts(unicos[i-1]['Data_Hora_Medicao'])
            t2 = parse_ts(it['Data_Hora_Medicao'])
            if t1 and t2 and (t2 - t1).total_seconds() > 1800:
                gaps += 1

    # Meses cobertos
    meses_cob = defaultdict(int)
    for it in unicos:
        mes = it['Data_Hora_Medicao'][:7]
        meses_cob[mes] += 1

    # Detecta eventos (cota > P95)
    p95 = sorted(cotas)[int(len(cotas) * 0.95)] if cotas else 0

    return {
        'total': total,
        'com_cota': com_cota,
        'pct_cota': com_cota / total * 100 if total else 0,
        'gaps': gaps,
        'pct_gaps': gaps / total * 100 if total else 0,
        'primeiro': unicos[0]['Data_Hora_Medicao'][:19],
        'ultimo': unicos[-1]['Data_Hora_Medicao'][:19],
        'cota_min': min(cotas) if cotas else None,
        'cota_max': max(cotas) if cotas else None,
        'p95': p95,
        'meses': dict(sorted(meses_cob.items())),
    }

def main():
    token = get_token()
    print(f"Token: {len(token)} chars")
    print(f"Auditoria: 12 meses por ancora\n")

    for bacia, (codigo, nome) in ANCORAS.items():
        print(f"\n{'='*80}")
        print(f"{bacia}: {codigo} — {nome}")
        print(f"{'='*80}")
        try:
            r = auditar_completo(token, codigo, meses=12)
        except Exception as e:
            print(f"  ERRO: {e}")
            continue
        if r is None:
            print(f"  SEM DADOS")
            continue
        print(f"  Total: {r['total']} leituras")
        print(f"  Com cota: {r['com_cota']} ({r['pct_cota']:.1f}%)")
        print(f"  Gaps >30min: {r['gaps']} ({r['pct_gaps']:.1f}%)")
        print(f"  Periodo: {r['primeiro']} a {r['ultimo']}")
        print(f"  Cota: {r['cota_min']:.1f} a {r['cota_max']:.1f} cm (P95={r['p95']:.0f})")
        print(f"  Meses:")
        for mes, n in sorted(r['meses'].items()):
            print(f"    {mes}: {n}")

if __name__ == "__main__":
    main()
