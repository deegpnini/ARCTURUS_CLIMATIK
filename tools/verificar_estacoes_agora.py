"""Verifica estado ATUAL das estacoes (ultimos 7 dias)."""
import json
import sys
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ana_auth import get_token

API = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"

ESTACOES = {
    "84580000": "Rio do Pouso (Tubarao) - ANCORA",
    "84249998": "Orleans-Montante",
    "84538500": "CGH Sao Mauricio",
    "84536000": "PCH Rio Fortuna",
    "83105000": "Saltinho (Itajai)",
}

token = get_token()
print("=" * 78)
print(f"  Estado ATUAL das estacoes — {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("=" * 78)
print()

for cod, nome in ESTACOES.items():
    query = (
        f"C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o={cod}"
        f"&Tipo%20Filtro%20Data=DATA_LEITURA"
        f"&Range%20Intervalo%20de%20busca=DIAS_7"
    )
    url = f"{API}?{query}"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})

    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            data = json.loads(r.read().decode("utf-8"))
            items = data.get("items") or []

            if not items:
                print(f"[{cod}] {nome}")
                print(f"  SEM DADOS nos ultimos 7 dias")
                print(f"  Msg: {data.get('message', 'sem mensagem')}")
                print()
                continue

            cotas = [i for i in items if i.get("Cota_Adotada") not in (None, "")]
            ultima = items[-1].get("Data_Hora_Medicao", "?")

            print(f"[{cod}] {nome}")
            print(f"  Total:         {len(items)} leituras")
            print(f"  Cota valida:   {len(cotas)} ({len(cotas)*100//len(items)}%)")
            print(f"  Ultima:        {ultima}")

            if cotas:
                u = cotas[-1]
                print(f"  Ultima cota:   {u.get('Cota_Adotada')} cm")
                print(f"  Data cota:     {u.get('Data_Hora_Medicao')}")
            print()

    except Exception as e:
        print(f"[{cod}] {nome}")
        print(f"  ERRO: {e}")
        print()
