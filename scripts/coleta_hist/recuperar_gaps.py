#!/usr/bin/env python3
"""
Recupera gaps do historico.
Puxa anos problematicos com DATA_LEITURA + DATA_ULTIMA_ATUALIZACAO.
Combina e normaliza.
"""
import json, os, sys, subprocess
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

HOME = os.path.expanduser("~")
CACHE = f"{HOME}/ARCTURUS_CLIMATIK/cache"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
CODIGO = "84580000"

def curl_ano(token, ano, filtro):
    url = (f"{BASE}/HidroSerieCotas/v1"
           f"?C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o={CODIGO}"
           f"&Tipo%20Filtro%20Data={filtro}"
           f"&Data%20Inicial%20(yyyy-MM-dd)={ano}-01-01"
           f"&Data%20Final%20(yyyy-MM-dd)={ano}-12-31")
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "60",
         "-H", f"Authorization: Bearer {token}", url],
        capture_output=True, text=True
    )
    try:
        return json.loads(r.stdout)
    except:
        return None

def extrair_cotas(items, ano):
    """Extrai cotas dos items, priorizando nc=2 depois 00h."""
    from datetime import datetime
    por_mes = {}
    for it in items:
        data_full = it.get('Data_Hora_Dado', '')
        if len(data_full) < 7: continue
        mes = data_full[:7]
        hora = data_full[11:13] if len(data_full) >= 13 else '00'
        nc = str(it.get('nivelconsistencia', '0'))
        score = 100 if nc == '2' else (50 if hora == '00' else 30 if hora == '07' else 20)
        if mes not in por_mes or score > por_mes[mes]['score']:
            por_mes[mes] = {'item': it, 'score': score}

    linhas = []
    for mes in sorted(por_mes.keys()):
        it = por_mes[mes]['item']
        ano_str, m = mes.split('-')
        for dia in range(1, 32):
            cota = it.get(f'Cota_{dia:02d}')
            if cota is None or cota == '': continue
            try:
                v = float(str(cota).replace(',', '.'))
            except: continue
            try:
                dt = f"{ano_str}-{m}-{dia:02d}"
                datetime.strptime(dt, "%Y-%m-%d")
            except: continue
            nc = str(it.get('nivelconsistencia', ''))
            linhas.append((dt, v, nc))
    return linhas

def main():
    token = get_token()
    anos = [1939, 2012, 2013, 2014, 2023, 2024, 2025]

    for ano in anos:
        print(f"\n=== {ano} ===")
        todas = {}

        for filtro in ['DATA_LEITURA', 'DATA_ULTIMA_ATUALIZACAO']:
            d = curl_ano(token, ano, filtro)
            if d and d.get("code") == 200:
                items = d.get("items", [])
                cotas = extrair_cotas(items, ano)
                print(f"  {filtro}: {len(cotas)} cotas")
                for dt, v, nc in cotas:
                    if dt not in todas:
                        todas[dt] = (v, nc, filtro)
            else:
                print(f"  {filtro}: sem dados")

        # Salva combinado
        linhas = ["data,cota,fonte,filtro"]
        for dt in sorted(todas.keys()):
            v, nc, filtro = todas[dt]
            linhas.append(f"{dt},{v:.2f},{nc},{filtro}")

        out = f"{CACHE}/cotas_{CODIGO}_{ano}_RECUPERADO.csv"
        with open(out, 'w') as f:
            f.write('\n'.join(linhas))
        print(f"  Total combinado: {len(todas)} dias")
        print(f"  Salvo: {out}")

if __name__ == "__main__":
    main()
