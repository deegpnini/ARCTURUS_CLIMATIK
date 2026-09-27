#!/usr/bin/env python3
"""
Retoma validacao quando estacao voltar.
Adiciona dados novos, valida previsoes pendentes.
"""
import json, os, sys, urllib.request
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
LOG = f"{CACHE}/previsoes_log.jsonl"
TEL = f"{CACHE}/telemetria_84580000_2026.json"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

def puxar_dias_2():
    token = get_token()
    url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
           f"?Codigos_Estacoes=84580000"
           f"&Tipo%20Filtro%20Data=DATA_LEITURA"
           f"&Range%20Intervalo%20de%20busca=DIAS_2")
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read().decode('utf-8'))

def main():
    print("=== RETOMAR VALIDACAO ===")
    print(f"Data/hora: {datetime.now()}")
    print()

    # Puxa dados novos
    d = puxar_dias_2()
    items = d.get('items', [])
    if not items:
        print("API ainda sem dados novos.")
        return

    items.sort(key=lambda x: x.get('Data_Hora_Medicao', ''))
    ultima = items[-1]
    print(f"Ultima leitura: {ultima.get('Data_Hora_Medicao')}")
    print(f"Cota: {ultima.get('Cota_Adotada')} cm")
    print()

    # Atualiza arquivo local
    if os.path.exists(TEL):
        with open(TEL) as f:
            local = json.load(f)
    else:
        local = {'items': []}

    existentes = {it.get('Data_Hora_Medicao') for it in local['items']}
    adicionados = 0
    for it in items:
        ts = it.get('Data_Hora_Medicao')
        if ts not in existentes:
            local['items'].append(it)
            adicionados += 1

    with open(TEL, 'w') as f:
        json.dump(local, f, default=str)
    print(f"Adicionados: {adicionados}")
    print(f"Total agora: {len(local['items'])}")

    # Verifica previsoes pendentes
    if os.path.exists(LOG):
        with open(LOG) as f:
            previsoes = [json.loads(l) for l in f.readlines()]

        print(f"\nPrevisoes no log: {len(previsoes)}")
        # Mapa de cota
        cotas = {}
        for it in local['items']:
            ts = it.get('Data_Hora_Medicao', '')[:19]
            c = it.get('Cota_Adotada')
            if c and c not in ('', '0.00'):
                try: cotas[ts] = float(str(c).replace(',', '.'))
                except: pass

        for p in previsoes:
            if 'validacao' in p:
                continue  # ja validada
            t0 = p.get('data_medicao', '')
            if not t0:
                continue
            try:
                dt0 = datetime.strptime(t0, "%Y-%m-%d %H:%M:%S")
            except:
                continue

            print(f"\nPrevisao em {t0}: cota {p.get('cota_atual')}")

            for h, horas in [('1h', 1), ('3h', 3), ('6h', 6)]:
                alvo = (dt0 + timedelta(hours=horas)).strftime("%Y-%m-%d %H:%M:%S")
                real = cotas.get(alvo)
                previsto = p['previsoes'][h]['cota']

                if real is not None:
                    erro = abs(previsto - real)
                    print(f"  {h}: prev {previsto:.1f} | real {real:.1f} | erro {erro:.1f}")
                else:
                    print(f"  {h}: alvo {alvo} sem dado")

if __name__ == "__main__":
    main()
