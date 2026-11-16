#!/usr/bin/env python3
"""
Monitor Rio do Pouso — usa DIAS_2 (HORA_24 bugado).
"""
import json, os, sys, subprocess
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

ESTACOES = {
    "84580000": "RIO DO POUSO (Tubarao)",
    "84580500": "TUBARAO",
    "84249998": "ORLEANS - MONTANTE",
    "84560000": "SAO LUDGERO I",
    "84610000": "GRAVATAL",
    "84680000": "USINA JORGE LACERDA",
    "84559800": "BRACO DO NORTE-MONTANTE",
}

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

def num(v):
    if v is None: return None
    try: return float(str(v).replace(',', '.'))
    except: return None

def main():
    token = get_token()
    print("="*80)
    print(f"MONITOR CRITICO — BACIA TUBARAO — {datetime.now()}")
    print("="*80)
    print()

    for cod, nome in ESTACOES.items():
        url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
               f"?Codigos_Estacoes={cod}"
               f"&Tipo%20Filtro%20Data=DATA_LEITURA"
               f"&Range%20Intervalo%20de%20busca=DIAS_2")
        d = curl_json(url, token)
        if not d or d.get("code") != 200:
            print(f"  {cod} {nome}: SEM DADOS ({d.get('message') if d else 'erro'})")
            continue
        
        items = d.get("items", [])
        if not items:
            print(f"  {cod} {nome}: SEM DADOS")
            continue
        
        items.sort(key=lambda x: x.get('Data_Hora_Medicao') or '')
        ultima = None
        for it in reversed(items):
            c = num(it.get('Cota_Adotada'))
            if c is not None:
                ultima = {'dt': it.get('Data_Hora_Medicao'), 'cota': c,
                          'vazao': num(it.get('Vazao_Adotada'))}
                break
        
        if ultima:
            print(f"  {cod} {nome}")
            print(f"    Cota: {ultima['cota']:.2f} cm")
            if ultima['vazao']:
                print(f"    Vazao: {ultima['vazao']:.2f} m3/s")
            print(f"    Em: {ultima['dt']}")
        else:
            print(f"  {cod} {nome}: sem cota valida")
        print()

if __name__ == "__main__":
    main()
