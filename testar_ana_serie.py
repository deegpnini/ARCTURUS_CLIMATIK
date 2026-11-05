#!/usr/bin/env python3
import requests
import os
from dotenv import load_dotenv

load_dotenv()
cpf = os.environ.get("ANA_CPF")
senha = os.environ.get("ANA_SENHA")

# Autentica
url_auth = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/OAUth/v1"
resp_auth = requests.get(url_auth, headers={"Identificador": cpf, "Senha": senha}, timeout=30)
token = resp_auth.json()["items"]["tokenautenticacao"]
headers = {"Authorization": f"Bearer {token}"}

url = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"

# Testa variações de parâmetros para a estação Rio do Pouso
testes = [
    {"codigoestacao": "84580000", "dataInicio": "2026-10-28", "dataFim": "2026-11-04"},
    {"codigoestacao": "84580000", "dataInicio": "28/10/2026", "dataFim": "04/11/2026"},
    {"codigoestacao": 84580000, "dataInicio": "2026-10-28", "dataFim": "2026-11-04"},
    {"codigoestacao": "84580000"},
]

for i, params in enumerate(testes, 1):
    print(f"\n=== Teste {i}: {params} ===")
    try:
        resp = requests.get(url, headers=headers, params=params, timeout=60)
        print(f"Status: {resp.status_code}")
        print(resp.text[:1500])
    except Exception as e:
        print(f"Erro: {e}")
