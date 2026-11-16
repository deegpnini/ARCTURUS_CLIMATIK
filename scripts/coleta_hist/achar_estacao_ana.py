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

url_inv = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroInventarioEstacoes/v1"
params_inv = {"Unidade Federativa": "SC"}
resp_inv = requests.get(url_inv, headers=headers, params=params_inv, timeout=60)
itens = resp_inv.json().get("items", [])

print(f"Total de estações em SC: {len(itens)}")
print("\n=== Estações da Bacia do Tubarão ===")
for est in itens:
    nome = est.get("Estacao_Nome", "")
    cod = est.get("Codigo_Estacao", est.get("codigoestacao", ""))
    sub = est.get("Sub_Bacia_Nome", "")
    tipo = est.get("Tipo_Estacao", "")
    if "TUBAR" in sub.upper() or "POUSO" in nome.upper() or "LUDGERO" in nome.upper() or "ORLEANS" in nome.upper():
        print(f"  Nome: {nome} | Código: {cod} | Tipo: {tipo} | Sub-Bacia: {sub}")
