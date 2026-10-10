import json, sys
from pathlib import Path
from datetime import date
sys.path.insert(0, '.')
from ana_auth import get_token
from urllib.request import Request, urlopen

tok = get_token()
hoje = date.today().strftime('%Y-%m-%d')
print(f"Buscando ancora 84580000 (data de busca: {hoje})")

query = (
    f"C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o=84580000"
    f"&Tipo%20Filtro%20Data=DATA_LEITURA"
    f"&Range%20Intervalo%20de%20busca=DIAS_7"
    f"&Data%20de%20Busca%20(yyyy-MM-dd)={hoje}"
)
url = f"https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1?{query}"
req = Request(url, headers={"Authorization": f"Bearer {tok}"})
with urlopen(req, timeout=60) as r:
    d = json.loads(r.read().decode("utf-8"))
    items = d.get("items") or []
    print(f"Items: {len(items)}")
    if items:
        print(f"Primeira:   {items[0].get('Data_Hora_Medicao')}")
        print(f"Ultima:     {items[-1].get('Data_Hora_Medicao')}")
        print(f"Cota ultima: {items[-1].get('Cota_Adotada')}")
        print()
        print("Ultimas 5 leituras:")
        for it in items[-5:]:
            print(f"  {it.get('Data_Hora_Medicao')} | cota: {it.get('Cota_Adotada')}")
    else:
        print(f"Mensagem da API: {d.get('message')}")
