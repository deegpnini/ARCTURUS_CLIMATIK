import json, sys, urllib.request, urllib.parse
from pathlib import Path
sys.path.insert(0, '.')
from ana_auth import get_token

tok = get_token()
URL = 'https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1'

for cod in ['84249998', '84538500', '84536000']:
    print(f'--- {cod} ---')
    q = urllib.parse.urlencode({
        'Codigo da Estacao': cod,
        'Tipo Filtro Data': 'DATA_LEITURA',
        'Range Intervalo de busca': 'DIAS_30'
    }, quote_via=urllib.parse.quote)
    # IMPORTANTE: os nomes reais tem espaco e acento. Codificar manualmente:
    q = 'C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o=' + cod + '&Tipo%20Filtro%20Data=DATA_LEITURA&Range%20Intervalo%20de%20busca=DIAS_30'
    req = urllib.request.Request(f'{URL}?{q}', headers={'Authorization': f'Bearer {tok}'})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode('utf-8'))
        its = d.get('items') or []
        print(f'  Total: {len(its)}')
        if its:
            cota_ok = sum(1 for x in its if x.get('Cota_Adotada') not in (None, ''))
            chuva_ok = sum(1 for x in its if x.get('Chuva_Adotada') not in (None, ''))
            print(f'  Cota valida: {cota_ok} ({cota_ok*100//len(its)}%)')
            print(f'  Chuva valida: {chuva_ok} ({chuva_ok*100//len(its)}%)')
            print(f'  Primeira: {its[0].get("Data_Hora_Medicao")}')
            print(f'  Ultima: {its[-1].get("Data_Hora_Medicao")}')
