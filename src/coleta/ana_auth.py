#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Autenticação na API nova da ANA (HidroWebService)."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_AUTH = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/OAUth/v1"

def get_token():
    cpf = os.environ.get("ANA_CPF")
    senha = os.environ.get("ANA_SENHA")
    if not cpf or not senha:
        raise ValueError("ANA_CPF e ANA_SENHA precisam estar no .env")
    
    headers = {"Identificador": cpf, "Senha": senha}
    resp = requests.get(BASE_AUTH, headers=headers, timeout=120)
    
    if resp.status_code != 200:
        raise RuntimeError(f"Falha na autenticação: {resp.status_code} - {resp.text[:200]}")
    
    data = resp.json()
    token = data.get("items", {}).get("tokenautenticacao")
    if not token:
        raise RuntimeError(f"Token não encontrado na resposta: {data}")
    
    return token

if __name__ == "__main__":
    token = get_token()
    print(f"Token: {len(token)} chars (OK)")
