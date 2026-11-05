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

# Endpoint e parâmetros EXATOS do manual (DATA_LEITURA, um T)
url = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"
params = {
    "CodigoDaEstacao": "84580000",
    "TipoFiltroData": "DATA_LEITURA",  # <-- UM "T" (correção)
    "RangeIntervaloDeBusca": "DIAS_30"
}

print(f"URL: {url}")
print(f"Params: {params}")
resp = requests.get(url, headers=headers, params=params, timeout=60)
print(f"Status: {resp.status_code}")
print(resp.text[:3000])
