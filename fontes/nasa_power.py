#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — NASA POWER (295 MUNICÍPIOS DE SC)
# ============================================================

import os
import csv
import json
import time
import urllib.request
import urllib.parse
from pathlib import Path
from datetime import datetime

# ============================================================
# CONFIGURAÇÃO
# ============================================================
BASE = Path.home() / "ARCTURUS_CLIMATIK"
DIRS = {
    "fontes": BASE / "fontes",
    "bronze": BASE / "dados" / "bronze" / "nasa",
    "climatologia": BASE / "climatologia",
    "logs": BASE / "logs",
}
for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

ANO_INICIO = 2020
ANO_FIM = 2025
MES_CLIMATOLOGIA = 9

PARAMETROS = [
    "T2M", "T2M_MAX", "T2M_MIN", "T2MDEW", "RH2M",
    "PRECTOTCORR", "WS10M", "PS", "GWETROOT", "GWETTOP", "EVPTRNS",
]

URL_BASE = "https://power.larc.nasa.gov/api/temporal/daily/point"

# ============================================================
# LOG
# ============================================================
def log(msg):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    with open(DIRS["logs"] / "nasa_power.log", "a", encoding="utf-8") as f:
        f.write(linha + "\n")

# ============================================================
# DOWNLOAD COM RETRY
# ============================================================
def baixar_nasa_power(lat, lon, max_tentativas=4):
    params = {
        "parameters": ",".join(PARAMETROS),
        "community": "AG",
        "longitude": str(lon),
        "latitude": str(lat),
        "start": f"{ANO_INICIO}0101",
        "end": f"{ANO_FIM}1231",
        "format": "JSON",
    }
    url = URL_BASE + "?" + urllib.parse.urlencode(params)
    headers = {"User-Agent": "ARCTURUS-CLIMATIK/1.0"}
    
    for tentativa in range(1, max_tentativas + 1):
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as resp:
                if resp.status == 200:
                    data = json.loads(resp.read().decode("utf-8"))
                    return data["properties"]["parameter"]
        except urllib.error.HTTPError as e:
            if e.code == 429:
                espera = 10 * tentativa
                log(f"    ⏸️  Rate limit. Aguardando {espera}s...")
                time.sleep(espera)
                continue
            if e.code == 422:
                return None
        except Exception as e:
            if tentativa < max_tentativas:
                time.sleep(5 * tentativa)
    return None

# ============================================================
# SALVAR BRONZE
# ============================================================
def salvar_bronze(codigo, nome, dados):
    if not dados:
        return None
    nome_arq = f"{codigo}_{nome.replace(' ', '_')}_{ANO_INICIO}_{ANO_FIM}.csv"
    arquivo = DIRS["bronze"] / nome_arq
    datas = sorted(dados[PARAMETROS[0]].keys())
    with open(arquivo, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["data"] + PARAMETROS)
        for data in datas:
            linha = [data] + [dados.get(p, {}).get(data) for p in PARAMETROS]
            w.writerow(linha)
    return arquivo

# ============================================================
# CLIMATOLOGIA
# ============================================================
def calcular_climatologia(codigo, nome, dados):
    if not dados:
        return None
    datas = sorted(dados[PARAMETROS[0]].keys())
    setembro = [d for d in datas if len(d) == 8 and d[4:6] == "09"]
    if not setembro:
        return None
    
    resultado = {"codigo_ibge": codigo, "cidade": nome, "ano_inicio": ANO_INICIO, "ano_fim": ANO_FIM}
    
    for p in PARAMETROS:
        valores = [dados[p][d] for d in setembro if dados[p].get(d) is not None]
        if not valores:
            continue
        valores_ord = sorted(valores)
        n = len(valores_ord)
        resultado[f"{p}_media"] = round(sum(valores) / n, 2)
        resultado[f"{p}_min"] = round(min(valores), 2)
        resultado[f"{p}_max"] = round(max(valores), 2)
        resultado[f"{p}_p10"] = round(valores_ord[int(n * 0.10)], 2)
        resultado[f"{p}_p90"] = round(valores_ord[int(n * 0.90)], 2)
    return resultado

# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 70)
    log("ARCTURUS — NASA POWER (TODOS OS MUNICÍPIOS DE SC)")
    log(f"Período: {ANO_INICIO}-{ANO_FIM} | Mês: {MES_CLIMATOLOGIA}")
    log(f"Parâmetros: {len(PARAMETROS)}")
    log("=" * 70)
    
    entrada = DIRS["fontes"] / "municipios_sc_coords.json"
    if not entrada.exists():
        log(f"❌ Arquivo não encontrado: {entrada}")
        return
    
    with open(entrada, "r", encoding="utf-8") as f:
        municipios = json.load(f)
    
    log(f"📍 {len(municipios)} municípios carregados")
    
    # Retomar do último processado
    clim_file = DIRS["climatologia"] / "nasa_setembro_completo.csv"
    ja_processados = set()
    clim_linhas = []
    
    if clim_file.exists():
        with open(clim_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                clim_linhas.append(row)
                ja_processados.add(str(row["codigo_ibge"]))
        log(f"✅ Retomando: {len(ja_processados)} já processados")
    
    log("")
    inicio = time.time()
    
    for i, m in enumerate(municipios, 1):
        codigo = str(m["codigo_ibge"])
        if codigo in ja_processados:
            continue
        
        nome = m["nome"]
        lat = m["lat"]
        lon = m["lon"]
        
        pct = (i / len(municipios)) * 100
        decorrido = time.time() - inicio
        processados_agora = i - len(ja_processados) if i > len(ja_processados) else 1
        eta = (decorrido / processados_agora) * (len(municipios) - i) if processados_agora > 0 else 0
        
        log(f"[{i:>3}/{len(municipios)} - {pct:>5.1f}%] {nome} (ETA: {eta/60:.1f}min)")
        
        dados = baixar_nasa_power(lat, lon)
        if not dados:
            log(f"    ❌ sem dados")
            time.sleep(2.5)
            continue
        
        salvar_bronze(codigo, nome, dados)
        clim = calcular_climatologia(codigo, nome, dados)
        if clim:
            clim_linhas.append(clim)
            ja_processados.add(codigo)
        
        # Salvar a cada 5
        if len(clim_linhas) % 5 == 0:
            _salvar_clim(clim_file, clim_linhas)
        
        time.sleep(2.5)
    
    if clim_linhas:
        _salvar_clim(clim_file, clim_linhas)
        log("")
        log(f"💾 Climatologia salva: {clim_file}")
        log(f"✅ Total: {len(clim_linhas)} municípios")
    
    duracao = (time.time() - inicio) / 60
    log(f"⏱️  Duração: {duracao:.1f} minutos")

def _salvar_clim(arquivo, linhas):
    colunas = ["codigo_ibge", "cidade", "ano_inicio", "ano_fim"]
    todas = set()
    for l in linhas:
        todas.update(l.keys())
    colunas += sorted([c for c in todas if c not in colunas])
    with open(arquivo, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas, extrasaction="ignore")
        w.writeheader()
        for l in linhas:
            w.writerow(l)

if __name__ == "__main__":
    main()
