#!/usr/bin/env python3
"""
Coletor historico ANA HidroSerieCotas — 84580000.
Checkpoint por ano. Retry. Rate-limit. Auditoria.
"""
import json, os, sys, subprocess, time
from datetime import datetime

sys.path.insert(0, os.path.expanduser("~/ARCTURUS_CLIMATIK"))
from ana_auth import get_token

HOME = os.path.expanduser("~")
CACHE = f"{HOME}/ARCTURUS_CLIMATIK/cache"
BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"
CODIGO = "84580000"
ANO_INI = 1939
ANO_FIM = 2026
CHECKPOINT = f"{CACHE}/coletor_checkpoint.json"

def curl_ano(token, ano):
    url = (f"{BASE}/HidroSerieCotas/v1"
           f"?C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o={CODIGO}"
           f"&Tipo%20Filtro%20Data=DATA_LEITURA"
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

def carregar_checkpoint():
    if os.path.exists(CHECKPOINT):
        with open(CHECKPOINT) as f:
            return json.load(f)
    return {"completos": [], "falhas": []}

def salvar_checkpoint(cp):
    with open(CHECKPOINT, "w") as f:
        json.dump(cp, f, indent=2)

def normalizar(ano_json_path, ano):
    """Gera CSV do ano. Retorna (meses, cotas, cobertura)."""
    from datetime import datetime
    d = json.load(open(ano_json_path))
    items = d.get("items", [])
    if not items:
        return 0, 0, 0

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

    linhas = ["data,cota,fonte_estacao,nc"]
    total = 0
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
            linhas.append(f"{dt},{v:.2f},{CODIGO},{nc}")
            total += 1

    # Salva CSV
    csv_path = f"{CACHE}/cotas_{CODIGO}_{ano}.csv"
    with open(csv_path, 'w') as f:
        f.write('\n'.join(linhas))

    # Cobertura esperada
    dias_esperados = 366 if (ano % 4 == 0 and (ano % 100 != 0 or ano % 400 == 0)) else 365
    return len(por_mes), total, dias_esperados

def main():
    token = get_token()
    print(f"Token: {len(token)} chars")
    cp = carregar_checkpoint()
    print(f"Checkpoint: {len(cp['completos'])} anos ja feitos")
    print()

    anos = list(range(ANO_INI, ANO_FIM + 1))
    resultados = []

    for i, ano in enumerate(anos, 1):
        if str(ano) in cp['completos']:
            continue

        print(f"[{i}/{len(anos)}] {ano}...", end=" ", flush=True)
        d = curl_ano(token, ano)

        if not d or d.get("code") != 200:
            print("FALHA")
            cp['falhas'].append(str(ano))
            salvar_checkpoint(cp)
            continue

        items = d.get("items", [])
        if not items:
            print("SEM DADOS")
            cp['completos'].append(str(ano))  # nao tem dado, mas tentou
            salvar_checkpoint(cp)
            continue

        # Salva RAW
        raw_path = f"{CACHE}/raw_{CODIGO}_{ano}.json"
        with open(raw_path, 'w') as f:
            json.dump({"ano": ano, "codigo": CODIGO, "items": items}, f, default=str)

        # Normaliza
        meses, cotas, esperados = normalizar(raw_path, ano)
        cobertura = (cotas / esperados * 100) if esperados else 0

        print(f"{meses} meses, {cotas} cotas, {cobertura:.0f}%")
        cp['completos'].append(str(ano))
        salvar_checkpoint(cp)

        time.sleep(0.5)  # rate limit

    print()
    print("="*60)
    print("RESUMO")
    print("="*60)
    print(f"Anos completos: {len(cp['completos'])}")
    print(f"Anos com falha: {len(cp['falhas'])}")

    if cp['falhas']:
        print(f"Falhas: {cp['falhas']}")

if __name__ == "__main__":
    main()
