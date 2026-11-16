#!/usr/bin/env python3
"""
Seleciona estacoes candidatas por bacia.
Auditoria de qualidade (nao treina nada).
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta
from collections import defaultdict

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
INV = f"{CACHE}/ana_inventario_sc.json"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

# Palavras-chave por bacia
BACIAS = {
    'ITAJAI_ACU': ['ITAJAI', 'BLUMENAU', 'RIO DO SUL', 'BRUSQUE', 'GASPAR', 'INDAIAL', 'NAVEGANTES', 'ILHOTA', 'ITAJAI-MIRIM', 'HERCILIO'],
    'ARARANGUA': ['ARARANGUA', 'CRICIUMA', 'SIDEROPOLIS', 'ICARA', 'TIMBE', 'ERMO', 'TURVO', 'FORQUILHINHA'],
    'CHAPECO': ['CHAPECO', 'CORONEL FREITAS', 'SAUDADES', 'QUILOMBO', 'NOVA ITABERABA', 'AGUAS DE CHAPECO'],
    'URUGUAI': ['URUGUAI', 'ITAPIRANGA', 'PALMITOS', 'MONDAI', 'SAO CARLOS', 'FOZ DO CHAPECO'],
    'TUBARAO': ['TUBARAO', 'ORLEANS', 'BRACO', 'LUDGERO', 'POUSO', 'GRAVATAL', 'CAPIVARI'],
}

def get_json(url, token, timeout=60):
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode('utf-8'))

def auditar_estacao(token, codigo, meses=6):
    """
    Puxa serie dos ultimos N meses em blocos de 30 dias.
    Conta: cobertura de cota, gaps, continuidade.
    """
    hoje = datetime.now()
    total_leituras = 0
    com_cota = 0
    gaps_grandes = 0
    primeiro = None
    ultimo = None

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
        items = d.get('items', []) if d else []
        if not items:
            continue

        items.sort(key=lambda x: x.get('Data_Hora_Medicao', ''))
        if primeiro is None:
            primeiro = items[0].get('Data_Hora_Medicao')

        ultima_t = None
        for it in items:
            total_leituras += 1
            c = it.get('Cota_Adotada')
            ts = it.get('Data_Hora_Medicao', '')[:19]
            if c and c not in ('', '0.00'):
                try:
                    float(str(c).replace(',', '.'))
                    com_cota += 1
                except:
                    pass
            if ultima_t:
                try:
                    d1 = datetime.strptime(ultima_t, "%Y-%m-%d %H:%M:%S")
                    d2 = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")
                    if (d2 - d1).total_seconds() > 1800:
                        gaps_grandes += 1
                except:
                    pass
            ultima_t = ts
            ultimo = ts

    return {
        'total_leituras': total_leituras,
        'com_cota': com_cota,
        'pct_cota': (com_cota / total_leituras * 100) if total_leituras else 0,
        'gaps_grandes': gaps_grandes,
        'primeiro': primeiro,
        'ultimo': ultimo,
    }

def main():
    token = get_token()
    print(f"Token: {len(token)} chars\n")

    with open(INV) as f:
        inv = json.load(f)
    items = inv.get('items', [])
    print(f"Inventario: {len(items)} estacoes SC\n")

    # Filtra fluviometricas + telemetrica + operando
    candidatas = []
    for x in items:
        tipo = str(x.get('Tipo_Estacao', '')).lower()
        tele = str(x.get('Tipo_Estacao_Telemetrica', '')).strip()
        oper = str(x.get('Operando', '')).strip()
        if 'fluvi' not in tipo or tele != '1' or oper != '1':
            continue
        nome = str(x.get('Estacao_Nome', '')).upper()
        municipio = str(x.get('Municipio_Nome', '')).upper()
        rio = str(x.get('Rio_Nome', '')).upper()
        junto = f"{nome} {municipio} {rio}"

        for bacia, palavras in BACIAS.items():
            if any(p in junto for p in palavras):
                candidatas.append({
                    'bacia': bacia,
                    'codigo': str(x.get('codigoestacao')),
                    'nome': x.get('Estacao_Nome'),
                    'municipio': x.get('Municipio_Nome'),
                    'rio': x.get('Rio_Nome'),
                })
                break

    print(f"Candidatas (fluviometrica+telemetrica+operando): {len(candidatas)}\n")

    # Agrupa por bacia
    por_bacia = defaultdict(list)
    for c in candidatas:
        por_bacia[c['bacia']].append(c)

    for bacia in BACIAS:
        lista = por_bacia.get(bacia, [])
        print(f"=== {bacia} === ({len(lista)} candidatas)")
        for c in lista[:10]:
            print(f"  {c['codigo']:12s} | {c['nome'][:40]:40s} | {c['municipio']}")
        if len(lista) > 10:
            print(f"  ... + {len(lista) - 10} outras")
        print()

    # Audita as principais de cada bacia (top 3)
    print("="*80)
    print("AUDITORIA DE QUALIDADE (top 3 por bacia, 3 meses)")
    print("="*80)
    print()

    for bacia in BACIAS:
        lista = por_bacia.get(bacia, [])
        print(f"\n--- {bacia} ---")
        for c in lista[:3]:
            print(f"  Auditando {c['codigo']} ({c['nome'][:30]})...")
            r = auditar_estacao(token, c['codigo'], meses=3)
            print(f"    Leituras: {r['total_leituras']} | cota: {r['com_cota']} ({r['pct_cota']:.1f}%) | gaps>30min: {r['gaps_grandes']}")
            print(f"    Periodo: {r['primeiro']} a {r['ultimo']}")

if __name__ == "__main__":
    main()
