#!/usr/bin/env python3
"""
ana_auth — autenticacao ANA com auto-renovacao.
Testa validade real (nao so timestamp).
"""
import os, json, urllib.request, subprocess
from datetime import datetime, timedelta

HOME = os.path.expanduser("~")
CACHE = f"{HOME}/ARCTURUS_CLIMATIK/cache"
TOKEN_FILE = f"{CACHE}/ana_token.txt"
META_FILE = f"{CACHE}/ana_token_meta.json"
ENV_FILE = f"{HOME}/ARCTURUS_CLIMATIK/.env"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

def carregar_env():
    env = {}
    if os.path.exists(ENV_FILE):
        with open(ENV_FILE) as f:
            for linha in f:
                if '=' in linha and not linha.startswith('#'):
                    k, v = linha.strip().split('=', 1)
                    env[k] = v
    return env

def autenticar():
    env = carregar_env()
    cpf = env.get('ANA_CPF')
    senha = env.get('ANA_SENHA')
    if not cpf or not senha:
        raise Exception("ANA_CPF/ANA_SENHA nao encontrados no .env")

    url = f"{BASE}/OAUth/v1"
    req = urllib.request.Request(url, headers={
        "accept": "*/*",
        "Identificador": cpf,
        "Senha": senha,
    })
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            d = json.loads(resp.read().decode('utf-8'))
            return d['items']['tokenautenticacao']
    except Exception as e:
        raise Exception(f"Auth falhou: {e}")

def testar_token(token):
    """Testa se o token funciona com HidroUF."""
    url = f"{BASE}/HidroUF/v1"
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = resp.read().decode('utf-8')
            return '"status":"OK"' in data
    except:
        return False

def get_token(force=False):
    # Tenta cache primeiro
    if not force and os.path.exists(TOKEN_FILE):
        with open(TOKEN_FILE) as f:
            tok = f.read().strip()
        if tok and testar_token(tok):
            return tok
    
    # Renova
    print("[ana_auth] Renovando token...")
    novo = autenticar()
    with open(TOKEN_FILE, 'w') as f:
        f.write(novo)
    os.chmod(TOKEN_FILE, 0o600)
    with open(META_FILE, 'w') as f:
        json.dump({
            'criado': datetime.now().isoformat(),
            'expira': (datetime.now() + timedelta(minutes=55)).isoformat(),
        }, f)
    return novo

if __name__ == "__main__":
    t = get_token()
    print(f"Token: {len(t)} chars")
    print(f"Valido: {testar_token(t)}")
