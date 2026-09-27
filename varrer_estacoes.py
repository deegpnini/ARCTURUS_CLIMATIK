#!/usr/bin/env python3
"""
VARREDURA ANA — Descobre quais estacoes de SC tem cota/vazao REAL.
Etapas:
  1. Inventario SC (ou usa cache)
  2. Filtro: Fluviometrica + Telemetrica=1 + Operando=1
  3. Consulta serie v2 de cada candidata (7 dias)
  4. Verifica Cota_Adotada/Vazao_Adotada != None em 20%+ das leituras
  5. Gera tabela final
"""
import json, os, subprocess, time
from collections import defaultdict

HOME = os.path.expanduser("~")
CACHE = f"{HOME}/ARCTURUS_CLIMATIK/cache"
TOKEN_FILE = f"{CACHE}/ana_token.txt"
INV_FILE = f"{CACHE}/ana_inventario_sc.json"
OUT_FILE = f"{CACHE}/ana_estacoes_utilizaveis.json"

BASE = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas"

def load_token():
    with open(TOKEN_FILE) as f:
        return f.read().strip()

def curl_json(url, token):
    """Faz GET com Bearer, retorna dict ou None."""
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "30",
         "-H", f"Authorization: Bearer {token}", url],
        capture_output=True, text=True
    )
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return None

def baixar_inventario(token):
    if os.path.exists(INV_FILE) and os.path.getsize(INV_FILE) > 10000:
        print(f"Inventario em cache: {INV_FILE}")
        with open(INV_FILE) as f:
            return json.load(f)
    
    print("Baixando inventario SC...")
    url = f"{BASE}/HidroInventarioEstacoes/v1?Unidade%20Federativa=SC"
    r = subprocess.run(
        ["curl", "-sS", "--max-time", "90",
         "-H", f"Authorization: Bearer {token}", url,
         "-o", INV_FILE],
        capture_output=True, text=True
    )
    with open(INV_FILE) as f:
        return json.load(f)

def filtrar_candidatas(inventario):
    """Fluviometrica + Telemetrica + Operando."""
    itens = inventario.get("items", [])
    candidatas = []
    for x in itens:
        tipo = str(x.get("Tipo_Estacao", "")).lower()
        tele = str(x.get("Tipo_Estacao_Telemetrica", "")).strip()
        oper = str(x.get("Operando", "")).strip()
        if "fluvi" in tipo and tele == "1" and oper == "1":
            candidatas.append({
                "codigo": str(x.get("codigoestacao") or x.get("Codigo_Estacao") or ""),
                "nome": x.get("Estacao_Nome"),
                "municipio": x.get("Municipio_Nome"),
                "rio": x.get("Rio_Nome"),
                "bacia": x.get("Bacia_Nome"),
                "lat": x.get("Latitude"),
                "lon": x.get("Longitude"),
            })
    return candidatas

def testar_serie(token, codigo):
    """Consulta serie v2, retorna dict com metricas."""
    url = (f"{BASE}/HidroinfoanaSerieTelemetricaAdotada/v2"
           f"?Codigos_Estacoes={codigo}"
           f"&Tipo%20Filtro%20Data=DATA_LEITURA"
           f"&Range%20Intervalo%20de%20busca=DIAS_7")
    d = curl_json(url, token)
    if not d or d.get("code") != 200:
        return {"erro": d.get("message") if d else "sem resposta"}
    
    itens = d.get("items", [])
    if not itens:
        return {"total": 0}
    
    total = len(itens)
    com_cota = sum(1 for x in itens if x.get("Cota_Adotada") not in (None, "", "0.00"))
    com_vazao = sum(1 for x in itens if x.get("Vazao_Adotada") not in (None, "", "0.00"))
    com_chuva = sum(1 for x in itens if x.get("Chuva_Adotada") not in (None, "", "0.00"))
    
    # Cota min/max
    cotas = []
    for x in itens:
        v = x.get("Cota_Adotada")
        if v not in (None, "", "0.00"):
            try: cotas.append(float(str(v).replace(",", ".")))
            except: pass
    
    return {
        "total": total,
        "com_cota": com_cota,
        "com_vazao": com_vazao,
        "com_chuva": com_chuva,
        "pct_cota": (com_cota / total * 100) if total else 0,
        "pct_vazao": (com_vazao / total * 100) if total else 0,
        "cota_min": min(cotas) if cotas else None,
        "cota_max": max(cotas) if cotas else None,
    }

def main():
    token = load_token()
    print(f"Token: {len(token)} chars\n")
    
    inv = baixar_inventario(token)
    print(f"Inventario: {len(inv.get('items', []))} estacoes SC\n")
    
    candidatas = filtrar_candidatas(inv)
    print(f"Candidatas (Fluviometrica + Telemetrica + Operando): {len(candidatas)}\n")
    
    if not candidatas:
        print("!! Nenhuma candidata — verificar filtros")
        return
    
    print("Testando serie de cada candidata (7 dias)...")
    print("(pode demorar ~1s por estacao)\n")
    
    resultados = []
    for i, c in enumerate(candidatas, 1):
        print(f"[{i}/{len(candidatas)}] {c['codigo']} {c['nome']}")
        metricas = testar_serie(token, c["codigo"])
        resultados.append({**c, **metricas})
        time.sleep(0.3)
    
    # Filtro final: tem cota E vazao em 20%+ das leituras
    utilizaveis = [
        r for r in resultados
        if r.get("pct_cota", 0) >= 20 and r.get("pct_vazao", 0) >= 20
    ]
    
    print("\n" + "="*100)
    print(f"RESULTADO: {len(utilizaveis)} estacoes utilizaveis (cota+vazao em 20%+ das leituras)")
    print("="*100)
    
    for r in sorted(utilizaveis, key=lambda x: -x["pct_cota"]):
        print(f"\n{r['codigo']} — {r['nome']}")
        print(f"  Municipio: {r['municipio']}")
        print(f"  Rio: {r['rio']}")
        print(f"  Bacia: {r['bacia']}")
        print(f"  Lat/Lon: {r['lat']}/{r['lon']}")
        print(f"  Leituras: {r['total']} (cota:{r['com_cota']} {r['pct_cota']:.1f}% | "
              f"vazao:{r['com_vazao']} {r['pct_vazao']:.1f}% | chuva:{r['com_chuva']})")
        if r["cota_min"] is not None:
            print(f"  Cota: {r['cota_min']:.2f} → {r['cota_max']:.2f}")
    
    # Salva resultado
    with open(OUT_FILE, "w") as f:
        json.dump({
            "total_candidatas": len(candidatas),
            "total_utilizaveis": len(utilizaveis),
            "estacoes": utilizaveis,
            "todas_testadas": resultados,
        }, f, indent=2, default=str)
    
    print(f"\n\nSalvo em: {OUT_FILE}")

if __name__ == "__main__":
    main()
