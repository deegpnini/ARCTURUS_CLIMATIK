import json
import pandas as pd
import requests
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]

# 1. Tentar acessar o histórico da ERAB via endpoint get_historico
print("=== TENTANDO ACESSAR O HISTÓRICO DA ERAB ===")
# O endpoint pode ser algo como /nivelriotubarao_termometro/get_historico
urls = [
    "https://tubaraosaneamento.com.br/nivelriotubarao_termometro/get_historico",
    "https://tubaraosaneamento.com.br/api/get_historico",
]
for url in urls:
    try:
        r = requests.get(url, timeout=10)
        print(f"URL: {url} | Status: {r.status_code}")
        if r.status_code == 200:
            print(f"  Resposta: {r.text[:300]}")
            break
    except Exception as e:
        print(f"  Erro: {e}")

# 2. Verificar o cache da ANA (84580000) e a data final
print("\n=== CACHE DA ANA (84580000) ===")
caminho_ana = BASE / "cache" / "ana_historico_84580000.json"
if caminho_ana.exists():
    with open(caminho_ana, "r") as f:
        dados = json.load(f)
    itens = dados.get("items", [])
    if itens:
        print(f"Total de leituras: {len(itens)}")
        print(f"Primeira: {itens[0].get('Data_Hora_Medicao')}")
        print(f"Última: {itens[-1].get('Data_Hora_Medicao')}")

# 3. Verificar o JSON da Tubarão Saneamento
print("\n=== JSON DA TUBARÃO SANEAMENTO ===")
caminho_erab = BASE / "tubarao_saneamento_dados.json"
if caminho_erab.exists():
    with open(caminho_erab, "r") as f:
        dados = json.load(f)
    print(f"Cota: {dados.get('cota_cm')} cm")
    print(f"Data: {dados.get('data_extracao')}")
