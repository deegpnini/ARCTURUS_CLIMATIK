#!/usr/bin/env python3
"""
Coleta telemetria 15min — 84580000 — 2024/2025/2026.
Salva por ano. Salva por mes (endpoint limita a 30 dias).
"""
import json, os, sys, subprocess, time
from datetime import datetime, timedelta

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

HOME = os.path.expanduser("~")
CACHE = f"{HOME}/ARCTURUS_CLIMATIK/cache"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
CODIGO = "84580000"

def curl_periodo(token, data_ini, data_fim):
    """Puxa periodo (max 30 dias)."""
    url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
           f"?Codigos_Estacoes={CODIGO}"
           f"&Tipo%20Filtro%20Data=DATA_LEITURA"
           f"&Range%20Intervalo%20de%20busca=DIAS_30"
           f"&Data%20de%20Busca%20(yyyy-MM-dd)={data_ini}")
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "60",
         "-H", f"Authorization: Bearer {token}", url],
        capture_output=True, text=True
    )
    try:
        d = json.loads(r.stdout)
        if d.get("code") == 200:
            return d.get("items", [])
    except:
        pass
    return None

def puxar_ano(token, ano):
    """Puxa ano inteiro em blocos de 30 dias."""
    print(f"\n=== {ano} ===")
    todos = []
    # 12 meses (aprox)
    for mes in range(1, 13):
        data = datetime(ano, mes, 1)
        data_str = data.strftime("%Y-%m-%d")
        print(f"  {data_str}...", end=" ", flush=True)
        items = curl_periodo(token, data_str, None)
        if items:
            print(f"{len(items)} leituras")
            todos.extend(items)
        else:
            print("vazio")
        time.sleep(0.5)

    # Deduplica por Data_Hora_Medicao
    vistos = set()
    unicos = []
    for it in todos:
        key = it.get('Data_Hora_Medicao')
        if key and key not in vistos:
            vistos.add(key)
            unicos.append(it)

    # Salva
    out = f"{CACHE}/telemetria_{CODIGO}_{ano}.json"
    with open(out, 'w') as f:
        json.dump({"ano": ano, "codigo": CODIGO, "items": unicos}, f, default=str)
    print(f"  -> {len(unicos)} leituras unicas salvas em {out}")
    return unicos

def main():
    token = get_token()
    print(f"Token: {len(token)} chars")

    for ano in [2024, 2025, 2026]:
        puxar_ano(token, ano)

if __name__ == "__main__":
    main()
