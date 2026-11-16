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

# Testa a rota de inventário (mais simples)
url_inv = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroInventarioEstacoes/v1"
params = {"codEstacao": "84580000"}
print(f"=== Testando inventário: {url_inv} ===")
resp = requests.get(url_inv, headers=headers, params=params, timeout=60)
print(f"Status: {resp.status_code}")
print(resp.text[:1500])
