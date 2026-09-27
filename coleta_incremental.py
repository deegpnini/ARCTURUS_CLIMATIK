#!/usr/bin/env python3
"""
Coleta incremental ANA — DIAS_2.
Usa urllib.request (stdlib). Upsert sem duplicacao.
"""
import json, os, sys, urllib.request
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

CACHE = "/data/data/com.termux/files/home/ARCTURUS_CLIMATIK/cache"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
CODIGO = "84580000"

def get_json(url, token):
    """GET com Bearer usando urllib (sem subprocess)."""
    req = urllib.request.Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = resp.read().decode('utf-8')
            return json.loads(data)
    except Exception as e:
        print(f"  ERRO urllib: {e}")
        return None

def carregar_existente(ano):
    path = f"{CACHE}/telemetria_{CODIGO}_{ano}.json"
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        d = json.load(f)
    items = d.get("items", [])
    return {it.get('Data_Hora_Medicao'): it for it in items if it.get('Data_Hora_Medicao')}

def salvar(ano, dict_items):
    path = f"{CACHE}/telemetria_{CODIGO}_{ano}.json"
    with open(path, 'w') as f:
        json.dump({
            "ano": int(ano),
            "codigo": CODIGO,
            "items": list(dict_items.values())
        }, f, default=str)
    return path

def coletar():
    token = get_token()
    print(f"Token: {len(token)} chars")
    print()

    # Coleta DIAS_2
    url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
           f"?Codigos_Estacoes={CODIGO}"
           f"&Tipo%20Filtro%20Data=DATA_LEITURA"
           f"&Range%20Intervalo%20de%20busca=DIAS_2")

    print("Coletando DIAS_2...")
    d = get_json(url, token)
    if not d or d.get("code") != 200:
        print(f"  ERRO: {d.get('message') if d else 'sem resposta'}")
        return

    novos = d.get("items", [])
    print(f"  Recebidos: {len(novos)} registros")

    # Agrupa por ano
    por_ano = {}
    for it in novos:
        ts = it.get('Data_Hora_Medicao', '')
        if not ts: continue
        ano = ts[:4]
        por_ano.setdefault(ano, []).append(it)

    for ano, items_novos in sorted(por_ano.items()):
        print(f"\n=== {ano} ===")

        existente = carregar_existente(ano)
        print(f"  Existente: {len(existente)} leituras")

        adicionados = 0
        atualizados = 0
        for it in items_novos:
            ts = it.get('Data_Hora_Medicao')
            if ts not in existente:
                existente[ts] = it
                adicionados += 1
            elif existente[ts] != it:
                existente[ts] = it
                atualizados += 1

        print(f"  Adicionados: {adicionados}")
        print(f"  Atualizados: {atualizados}")
        print(f"  Total agora: {len(existente)}")

        path = salvar(ano, existente)
        print(f"  Salvo: {path}")

if __name__ == "__main__":
    coletar()
