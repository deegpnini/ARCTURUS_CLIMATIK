#!/usr/bin/env python3
"""
Auditoria fina: 4 testes.
Sem treinar. So investigacao.
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

def get_json(url, token, timeout=60):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def puxar(token, codigo, meses=12):
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
    return unicos

def analisar_cota_ausente(leituras, codigo, nome):
    """Ver o que tem nos 29% sem cota."""
    print(f"\n--- TESTE 1: {codigo} {nome} ---")

    total = len(leituras)
    com_cota = 0
    sem_cota_zero = 0  # cota = "0.00"
    sem_cota_none = 0  # cota = None
    sem_cota_vazio = 0  # cota = ""
    sem_cota_outro = 0

    for it in leituras:
        c = it.get('Cota_Adotada')
        if c is None:
            sem_cota_none += 1
        elif c == '':
            sem_cota_vazio += 1
        elif c == '0.00' or c == '0':
            sem_cota_zero += 1
        else:
            try:
                float(str(c).replace(',', '.'))
                com_cota += 1
            except:
                sem_cota_outro += 1

    print(f"  Total leituras: {total}")
    print(f"  Com cota: {com_cota} ({com_cota/total*100:.1f}%)")
    print(f"  None: {sem_cota_none} ({sem_cota_none/total*100:.1f}%)")
    print(f"  Vazio: {sem_cota_vazio} ({sem_cota_vazio/total*100:.1f}%)")
    print(f"  Zero (0.00): {sem_cota_zero} ({sem_cota_zero/total*100:.1f}%)")
    print(f"  Outro (nao numerico): {sem_cota_outro}")

    # Se o ausente for 'None' puro, ver se e' padrao (todo dia ou periodos)
    if sem_cota_none > 0:
        amostra = [it['Data_Hora_Medicao'][:10] for it in leituras if it.get('Cota_Adotada') is None]
        dias = defaultdict(int)
        for d in amostra:
            dias[d] += 1
        print(f"  Distribuicao por dia (top 5):")
        for d, n in sorted(dias.items(), key=lambda x: -x[1])[:5]:
            print(f"    {d}: {n}")

def analisar_gap(leituras, codigo, nome, min_horas=24):
    """Encontrar gaps grandes e ver quando acontecem."""
    print(f"\n--- TESTE 2: GAPS > {min_horas}h em {codigo} {nome} ---")

    def p(s):
        try: return datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S")
        except: return None

    gaps = []
    for i in range(1, len(leituras)):
        t1 = p(leituras[i-1]['Data_Hora_Medicao'])
        t2 = p(leituras[i]['Data_Hora_Medicao'])
        if t1 and t2:
            d = (t2 - t1).total_seconds() / 3600
            if d > min_horas:
                gaps.append({
                    'de': leituras[i-1]['Data_Hora_Medicao'][:19],
                    'para': leituras[i]['Data_Hora_Medicao'][:19],
                    'horas': d,
                })

    print(f"  Total gaps > {min_horas}h: {len(gaps)}")
    for g in sorted(gaps, key=lambda x: -x['horas'])[:5]:
        print(f"    {g['de']} -> {g['para']} ({g['horas']:.0f}h = {g['horas']/24:.1f} dias)")

def testar_epagri(codigo, nome):
    """Testa se EPAGRI responde (site publico)."""
    print(f"\n--- TESTE 4: EPAGRI/CIRAM para {codigo} {nome} ---")
    try:
        url = "https://ciram.epagri.sc.gov.br/"
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=15) as r:
            data = r.read().decode('utf-8', errors='ignore')
            print(f"  EPAGRI respondeu: {len(data)} bytes")
            if 'epagri' in data.lower() or 'ciram' in data.lower():
                print(f"  -> site acessivel, mas scraping precisa ser desenvolvido")
    except Exception as e:
        print(f"  ERRO: {e}")

def main():
    token = get_token()
    print(f"Token: {len(token)} chars")

    # TESTE 1: Saltinho - cota ausente
    print("\n" + "="*70)
    print("TESTE 1: SALTINHO (83105000)")
    print("="*70)
    leituras_salt = puxar(token, '83105000', meses=12)
    if leituras_salt:
        analisar_cota_ausente(leituras_salt, '83105000', 'Saltinho')
    else:
        print("SEM DADOS")

    # TESTE 2: Rio do Sul - gap de 154 dias
    print("\n" + "="*70)
    print("TESTE 2: RIO DO SUL (83300200)")
    print("="*70)
    leituras_rs = puxar(token, '83300200', meses=12)
    if leituras_rs:
        analisar_gap(leituras_rs, '83300200', 'Rio do Sul', min_horas=24)

    # TESTE 3: Ermo - voltou?
    print("\n" + "="*70)
    print("TESTE 3: ERMO (84949800)")
    print("="*70)
    leituras_ermo = puxar(token, '84949800', meses=6)
    if leituras_ermo:
        print(f"  Primeiro: {leituras_ermo[0]['Data_Hora_Medicao'][:19]}")
        print(f"  Ultimo:   {leituras_ermo[-1]['Data_Hora_Medicao'][:19]}")
        print(f"  Total: {len(leituras_ermo)}")
    else:
        print("  SEM DADOS nos ultimos 6 meses")

    # TESTE 4: EPAGRI
    print("\n" + "="*70)
    print("TESTE 4: EPAGRI/CIRAM")
    print("="*70)
    testar_epagri('', '')

    print("\n" + "="*70)
    print("FIM DA AUDITORIA FINA")
    print("="*70)

if __name__ == "__main__":
    main()
