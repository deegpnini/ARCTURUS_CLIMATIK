#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

load_dotenv()

cpf = os.environ.get("ANA_CPF")
senha = os.environ.get("ANA_SENHA")

url_auth = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/OAUth/v1"
resp_auth = requests.get(url_auth, headers={"Identificador": cpf, "Senha": senha}, timeout=30)
token = resp_auth.json()["items"]["tokenautenticacao"]
headers = {"Authorization": f"Bearer {token}"}

url = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"

# Testa variações de parâmetros
testes = [
    {"codEstacao": "84580000", "dataInicio": "2026-10-28", "dataFim": "2026-11-04"},
    {"codEstacao": "84580000", "dataInicio": "28/10/2026", "dataFim": "04/11/2026"},
    {"codEstacao": "84580000", "dataInicio": "2026-10-28T00:00:00", "dataFim": "2026-11-04T23:59:59"},
    {"codEstacao": "84580000"},
    {"codEstacao": "84580000", "dataInicio": "20261028", "dataFim": "20261104"},
    {"codEstacao": "84580000", "dataInicio": "2026-10-28", "dataFim": "2026-11-04", "tipoDado": "1"},
    {"codEstacao": "84580000", "dataInicio": "2026-10-28", "dataFim": "2026-11-04", "nivelConsistencia": "1"},
]

for i, params in enumerate(testes, 1):
    print(f"\n=== Teste {i}: {params} ===")
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        print(f"Status: {resp.status_code}")
        print(resp.text[:600])
    except Exception as e:
        print(f"Erro: {e}")
