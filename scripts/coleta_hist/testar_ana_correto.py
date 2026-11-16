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

# 1) Inventário de SC (para achar a estação)
url_inv = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroInventarioEstacoes/v1"
params_inv = {"Unidade Federativa": "SC"}
print(f"=== Inventário SC ===")
resp_inv = requests.get(url_inv, headers=headers, params=params_inv, timeout=60)
print(f"Status: {resp_inv.status_code}")
print(resp_inv.text[:2000])

# 2) Série da estação (com o nome correto do parâmetro)
url_serie = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"
params_serie = {"codigoestacao": "84580000", "dataInicio": "2026-10-28", "dataFim": "2026-11-04"}
print(f"\n=== Série 84580000 (codigoestacao) ===")
resp_serie = requests.get(url_serie, headers=headers, params=params_serie, timeout=60)
print(f"Status: {resp_serie.status_code}")
print(resp_serie.text[:1500])
