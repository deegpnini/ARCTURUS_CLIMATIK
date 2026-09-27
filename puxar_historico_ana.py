#!/usr/bin/env python3
"""
Puxa serie historica longa da ANA via paginacao.
Range maximo por requisicao: DIAS_30
Para historico maior: multiplas requisicoes com Data_Busca retroativo.
"""
import json, os, subprocess
from datetime import datetime, timedelta

HOME = os.path.expanduser("~")
CACHE = f"{HOME}/ARCTURUS_CLIMATIK/cache"
TOKEN_FILE = f"{CACHE}/ana_token.txt"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

def get_token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()

def curl_json(url, token):
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "60",
         "-H", f"Authorization: Bearer {token}", url],
        capture_output=True, text=True
    )
    try:
        return json.loads(r.stdout)
    except:
        return None

def puxar_periodo(token, codigo, data_inicio, data_fim):
    """Puxa serie de um periodo (max 30 dias)."""
    url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
           f"?Codigos_Estacoes={codigo}"
           f"&Tipo%20Filtro%20Data=DATA_LEITURA"
           f"&Range%20Intervalo%20de%20busca=DIAS_30"
           f"&Data%20de%20Busca%20(yyyy-MM-dd)={data_inicio}")
    d = curl_json(url, token)
    if not d or d.get("code") != 200:
        return []
    return d.get("items", [])

def puxar_historico(token, codigo, meses_atras=6):
    """Puxa N meses de historico paginando em blocos de 30 dias."""
    hoje = datetime.now()
    todas = []
    
    for i in range(meses_atras):
        # Data de busca = inicio do mes retroativo
        data = hoje - timedelta(days=30 * (i+1))
        data_str = data.strftime("%Y-%m-%d")
        
        print(f"  [{i+1}/{meses_atras}] puxando {data_str}...")
        items = puxar_periodo(token, codigo, data_str, None)
        if items:
            todas.extend(items)
            print(f"    -> {len(items)} leituras")
    
    # Ordena por timestamp
    todas.sort(key=lambda x: x.get("Data_Hora_Medicao") or "")
    return todas

def main():
    token = get_token()
    print(f"Token: {len(token)} chars\n")
    
    # Estacoes alvo: Rio do Pouso + Orleans + outras naturais
    estacoes = {
        "84580000": "RIO DO POUSO (Tubarao)",
        "84249998": "ORLEANS (pluviometrica)",
    }
    
    for codigo, nome in estacoes.items():
        print(f"\n{'='*60}")
        print(f"PUXANDO {codigo} — {nome}")
        print('='*60)
        
        items = puxar_historico(token, codigo, meses_atras=6)
        
        if items:
            out = f"{CACHE}/ana_historico_{codigo}.json"
            with open(out, 'w') as f:
                json.dump({"codigo": codigo, "nome": nome, "items": items}, f, default=str)
            print(f"\n  ✅ salvo: {out}")
            print(f"  total: {len(items)} leituras")
            print(f"  periodo: {items[0]['Data_Hora_Medicao']} a {items[-1]['Data_Hora_Medicao']}")
        else:
            print(f"\n  ❌ nenhum dado")

if __name__ == "__main__":
    main()
