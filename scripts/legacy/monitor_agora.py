#!/usr/bin/env python3
"""
Monitor Rio do Pouso (84580000).
Usa DIAS_7 (endpoint funciona) e filtra ultimas 24h no codigo.
"""
import json, os, sys, subprocess
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

def curl_json(url, token):
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "30",
         "-H", f"Authorization: Bearer {token}", url],
        capture_output=True, text=True
    )
    try:
        return json.loads(r.stdout)
    except:
        return None

def numero(v):
    if v is None: return None
    try: return float(str(v).replace(',', '.'))
    except: return None

def main():
    token = get_token()
    url = ("https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/"
           "HidroinfoanaSerieTelemetricaAdotada/v2"
           "?Codigos_Estacoes=84580000"
           "&Tipo%20Filtro%20Data=DATA_LEITURA"
           "&Range%20Intervalo%20de%20busca=DIAS_7")

    d = curl_json(url, token)
    if not d or d.get("code") != 200:
        print(f"Erro na API: {d.get('message') if d else 'sem resposta'}")
        return

    items = d.get("items", [])
    if not items:
        print("Sem leituras nos ultimos 7 dias")
        return

    items.sort(key=lambda x: x.get('Data_Hora_Medicao') or '')

    leituras = []
    for it in items:
        cota = numero(it.get('Cota_Adotada'))
        if cota is not None:
            leituras.append({
                'dt': it.get('Data_Hora_Medicao', '')[:19],
                'cota': cota,
                'chuva': numero(it.get('Chuva_Adotada')),
                'vazao': numero(it.get('Vazao_Adotada')),
            })

    if not leituras:
        print("Sem leituras validas")
        return

    atual = leituras[-1]
    ultima_leit = leituras[-1]['dt']

    def mais_proximo(dt_alvo_str):
        for l in reversed(leituras):
            if l['dt'] <= dt_alvo_str:
                return l
        return None

    dt_atual = datetime.strptime(atual['dt'], "%Y-%m-%d %H:%M:%S")
    l_15m = mais_proximo((dt_atual - timedelta(minutes=15)).strftime("%Y-%m-%d %H:%M:%S"))
    l_30m = mais_proximo((dt_atual - timedelta(minutes=30)).strftime("%Y-%m-%d %H:%M:%S"))
    l_1h = mais_proximo((dt_atual - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S"))
    l_6h = mais_proximo((dt_atual - timedelta(hours=6)).strftime("%Y-%m-%d %H:%M:%S"))

    agora = datetime.now()
    delta_horas = (agora - dt_atual).total_seconds() / 3600

    print("="*60)
    print("MONITOR RIO DO POUSO (84580000)")
    print("="*60)
    print(f"Ultima leitura: {atual['dt']}")
    print(f"Tempo desde entao: {delta_horas:.1f}h")
    print(f"Cota atual: {atual['cota']:.2f}")
    if atual['vazao']:
        print(f"Vazao atual: {atual['vazao']:.2f} m3/s")
    print()

    if delta_horas > 2:
        print(f"⚠️  ATENCAO: estacao nao reporta ha {delta_horas:.1f}h")
        print("   (pode ser perda de sinal durante evento)")
        print()

    print("TENDENCIA:")
    if l_15m:
        delta = atual['cota'] - l_15m['cota']
        print(f"  vs 15min atras: {l_15m['cota']:.2f} -> {atual['cota']:.2f}  (delta {delta:+.2f})")
    if l_30m:
        delta = atual['cota'] - l_30m['cota']
        print(f"  vs 30min atras: {l_30m['cota']:.2f} -> {atual['cota']:.2f}  (delta {delta:+.2f})")
    if l_1h:
        delta = atual['cota'] - l_1h['cota']
        print(f"  vs 1h atras:    {l_1h['cota']:.2f} -> {atual['cota']:.2f}  (delta {delta:+.2f})")
    if l_6h:
        delta = atual['cota'] - l_6h['cota']
        print(f"  vs 6h atras:    {l_6h['cota']:.2f} -> {atual['cota']:.2f}  (delta {delta:+.2f})")
    print()

    if l_1h:
        delta_1h = atual['cota'] - l_1h['cota']
        if delta_1h > 30:
            print("CLASSIFICACAO:  ^^ SUBINDO RAPIDO")
        elif delta_1h > 10:
            print("CLASSIFICACAO:  ^ SUBINDO")
        elif delta_1h > -5:
            print("CLASSIFICACAO:  = ESTAVEL")
        elif delta_1h > -15:
            print("CLASSIFICACAO:  v DESCENDO")
        else:
            print("CLASSIFICACAO:  vv DESCENDO RAPIDO")

    # Chuva nas ultimas 24h
    if leituras:
        dt_24h = (dt_atual - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        chuva_24h = sum(l['chuva'] for l in leituras if l['chuva'] is not None and l['dt'] >= dt_24h)
        print()
        print(f"CHUVA 24h: {chuva_24h:.2f} mm")

if __name__ == "__main__":
    main()
