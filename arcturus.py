#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — MOTOR v3.4
# CAPE + Lifted Index + Tempestades Severas
# ============================================================

import os
import csv
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path.home() / "ARCTURUS_CLIMATIK"
DIRS = {
    "fontes": BASE / "fontes",
    "climatologia": BASE / "climatologia",
    "relatorios": BASE / "relatorios",
    "logs": BASE / "logs",
    "cache": BASE / "cache",
}
for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

CIDADES_COORDS = DIRS["fontes"] / "municipios_sc_coords.json"
CLIMATOLOGIA = DIRS["climatologia"] / "nasa_setembro_completo.csv"
CACHE_FILE = DIRS["cache"] / "arcturus_alerta.json"

# ============================================================
# LOG
# ============================================================
def log(msg):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    with open(DIRS["logs"] / "motor_v34.log", "a", encoding="utf-8") as f:
        f.write(linha + "\n")

# ============================================================
# CARREGAR DADOS
# ============================================================
def carregar_climatologia():
    if not CLIMATOLOGIA.exists():
        return {}
    clim = {}
    with open(CLIMATOLOGIA, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            cod = row.get("codigo_ibge", "").strip()
            if cod:
                clim[cod] = row
    log(f"✅ Climatologia: {len(clim)} municípios")
    return clim

def carregar_coordenadas():
    if not CIDADES_COORDS.exists():
        return []
    with open(CIDADES_COORDS, "r", encoding="utf-8") as f:
        cidades = json.load(f)
    log(f"✅ Coordenadas: {len(cidades)} municípios")
    return cidades

# ============================================================
# CONSULTAR OPEN-METEO (com CAPE + LI)
# ============================================================
def consultar_openmeteo(lat, lon):
    """Consulta Open-Meteo incluindo CAPE e Lifted Index."""
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,"
        f"wind_speed_10m,wind_gusts_10m,precipitation,"
        f"cape,lifted_index,cloud_cover"
        f"&timezone=America/Sao_Paulo"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ARCTURUS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8"))
            c = data.get("current", {})
            return {
                "temperatura": c.get("temperature_2m"),
                "umidade": c.get("relative_humidity_2m"),
                "vento": c.get("wind_speed_10m"),
                "rajada": c.get("wind_gusts_10m"),
                "precipitacao": c.get("precipitation"),
                "cape": c.get("cape"),
                "lifted_index": c.get("lifted_index"),
                "nuvens": c.get("cloud_cover"),
            }
    except Exception as e:
        return None

# ============================================================
# ANALISAR TEMPESTADE SEVERA
# ============================================================
def analisar_tempestade(cape, li, vento, rajada):
    """Detecta risco de tempestade severa, granizo e vendaval."""
    alertas = []
    status_tempestade = "🟢 SEM RISCO"
    
    if cape is None or li is None:
        return "⚪ SEM DADOS", []
    
    # Classificação por CAPE
    if cape >= 4000:
        status_tempestade = "🔴 EXTREMO"
        alertas.append(f"CAPE extremo: {cape} J/kg — risco de tornado/supercélula")
    elif cape >= 2500:
        status_tempestade = "🔴 ALERTA VERMELHO"
        alertas.append(f"CAPE muito alto: {cape} J/kg — risco de granizo grande")
    elif cape >= 1500:
        status_tempestade = "🟠 ALERTA LARANJA"
        alertas.append(f"CAPE elevado: {cape} J/kg — tempestade forte possível")
    elif cape >= 1000:
        status_tempestade = "🟡 ATENÇÃO"
        alertas.append(f"CAPE moderado: {cape} J/kg — instabilidade")
    
    # Classificação por Lifted Index
    if li <= -6:
        alertas.append(f"Lifted Index crítico: {li} — supercélulas")
        if status_tempestade == "🟢 SEM RISCO":
            status_tempestade = "🔴 ALERTA VERMELHO"
    elif li <= -4:
        alertas.append(f"Lifted Index severo: {li} — tempestades severas")
        if status_tempestade == "🟢 SEM RISCO":
            status_tempestade = "🟠 ALERTA LARANJA"
    elif li <= -2:
        alertas.append(f"Lifted Index instável: {li}")
        if status_tempestade == "🟢 SEM RISCO":
            status_tempestade = "🟡 ATENÇÃO"
    
    # Vendaval (rajadas fortes)
    if rajada is not None and rajada >= 80:
        alertas.append(f"Rajadas extremas: {rajada} km/h — vendaval")
        if status_tempestade == "🟢 SEM RISCO":
            status_tempestade = "🔴 ALERTA VERMELHO"
    elif rajada is not None and rajada >= 60:
        alertas.append(f"Rajadas fortes: {rajada} km/h")
        if status_tempestade == "🟢 SEM RISCO":
            status_tempestade = "🟠 ALERTA LARANJA"
    
    return status_tempestade, alertas

# ============================================================
# ANALISAR ANOMALIA CLIMÁTICA
# ============================================================
def analisar_clima(dados, clim):
    if not dados or not clim:
        return None
    temp = dados.get("temperatura")
    umid = dados.get("umidade")
    chuva = dados.get("precipitacao")
    if temp is None:
        return None
    try:
        temp_media = float(clim.get("T2M_media", 0))
        temp_min_p10 = float(clim.get("T2M_MIN_p10", 0))
        temp_max_p90 = float(clim.get("T2M_MAX_p90", 0))
        umid_media = float(clim.get("RH2M_media", 0))
        chuva_p90 = float(clim.get("PRECTOTCORR_p90", 0))
    except (ValueError, TypeError):
        return None
    
    analise = {
        "cidade": dados.get("cidade", "?"),
        "codigo_ibge": dados.get("codigo_ibge", ""),
        "temperatura": temp,
        "temp_media_clim": temp_media,
        "desvio_temp": round(temp - temp_media, 1),
        "umidade": umid,
        "chuva": chuva,
        "vento": dados.get("vento"),
        "rajada": dados.get("rajada"),
        "cape": dados.get("cape"),
        "lifted_index": dados.get("lifted_index"),
        "nuvens": dados.get("nuvens"),
        "status_clima": "🟢 NORMAL",
        "status_tempestade": "🟢 SEM RISCO",
        "alertas": [],
        "alertas_tempestade": [],
    }
    
    # Anomalias climáticas
    if temp < temp_min_p10:
        analise["status_clima"] = "🔵 FRIO ANORMAL"
        analise["alertas"].append(f"Temp {temp}°C abaixo do p10 ({temp_min_p10}°C)")
    elif temp > temp_max_p90:
        analise["status_clima"] = "🔴 CALOR ANORMAL"
        analise["alertas"].append(f"Temp {temp}°C acima do p90 ({temp_max_p90}°C)")
    elif abs(analise["desvio_temp"]) >= 3:
        analise["status_clima"] = "🟡 ATENÇÃO"
        analise["alertas"].append(f"Desvio de {analise['desvio_temp']}°C")
    
    if umid is not None and umid >= 90:
        analise["alertas"].append(f"Umidade alta: {umid}%")
    
    if chuva is not None and chuva >= chuva_p90:
        analise["alertas"].append(f"Chuva {chuva}mm ≥ p90 ({chuva_p90}mm)")
    
    # Tempestade severa
    status_temp, alertas_temp = analisar_tempestade(
        dados.get("cape"),
        dados.get("lifted_index"),
        dados.get("vento"),
        dados.get("rajada")
    )
    analise["status_tempestade"] = status_temp
    analise["alertas_tempestade"] = alertas_temp
    
    return analise

# ============================================================
# CACHE
# ============================================================
def salvar_cache(analises):
    """Salva cache com anomalias climáticas + tempestades."""
    anomalias_clima = [a for a in analises if a and a["status_clima"] != "🟢 NORMAL"]
    tempestades = [a for a in analises if a and a["status_tempestade"] != "🟢 SEM RISCO"]
    
    cache = {
        "ultima_atualizacao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "total_municipios": len(analises),
        "anomalias_clima": len(anomalias_clima),
        "tempestades_severas": len(tempestades),
        "status_geral": "ALERTA" if (anomalias_clima or tempestades) else "NORMAL",
        "cidades_clima_anormal": anomalias_clima,
        "cidades_tempestade": tempestades,
        "resumo": {
            "normais": len([a for a in analises if a and a["status_clima"] == "🟢 NORMAL" and a["status_tempestade"] == "🟢 SEM RISCO"]),
            "atencao_clima": len([a for a in analises if a and a["status_clima"] == "🟡 ATENÇÃO"]),
            "frio_anormal": len([a for a in analises if a and a["status_clima"] == "🔵 FRIO ANORMAL"]),
            "calor_anormal": len([a for a in analises if a and a["status_clima"] == "🔴 CALOR ANORMAL"]),
            "tempestades": len(tempestades),
        },
    }
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)
    
    return cache

# ============================================================
# RELATÓRIO
# ============================================================
def gerar_relatorio(analises):
    agora = datetime.now()
    arquivo = DIRS["relatorios"] / f"motor_{agora.strftime('%Y%m%d_%H%M')}.txt"
    
    with open(arquivo, "w", encoding="utf-8") as f:
        f.write("=" * 70 + "\n")
        f.write("🟣 ARCTURUS CLIMATIK — RELATÓRIO v3.4\n")
        f.write("=" * 70 + "\n")
        f.write(f"📅 {agora.strftime('%d/%m/%Y %H:%M')}\n")
        f.write(f"📍 SC — {len(analises)} municípios\n")
        f.write("=" * 70 + "\n\n")
        
        anomalias = [a for a in analises if a and a["status_clima"] != "🟢 NORMAL"]
        tempestades = [a for a in analises if a and a["status_tempestade"] != "🟢 SEM RISCO"]
        
        f.write(f"⚠️  ANOMALIAS CLIMÁTICAS: {len(anomalias)}\n")
        for a in anomalias:
            f.write(f"  {a['cidade']:<25} {a['status_clima']} | {a['temperatura']}°C\n")
        
        f.write(f"\n⛈️  TEMPESTADES SEVERAS: {len(tempestades)}\n")
        for a in tempestades:
            f.write(f"  {a['cidade']:<25} {a['status_tempestade']}\n")
            for alerta in a["alertas_tempestade"]:
                f.write(f"      → {alerta}\n")
        
        f.write("\n" + "=" * 70 + "\n")
    
    return arquivo

# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 70)
    log("🟣 ARCTURUS CLIMATIK — MOTOR v3.4 (CAPE + LI)")
    log("=" * 70)
    
    clim = carregar_climatologia()
    cidades = carregar_coordenadas()
    
    if not clim or not cidades:
        log("❌ Dados insuficientes")
        return
    
    log(f"📊 Processando {len(cidades)} municípios...")
    
    analises = []
    inicio = time.time()
    
    for i, cidade in enumerate(cidades, 1):
        codigo = str(cidade["codigo_ibge"])
        nome = cidade["nome"]
        
        if i % 50 == 0 or i == 1:
            log(f"[{i:>3}/{len(cidades)}] {nome}")
        
        dados = consultar_openmeteo(cidade["lat"], cidade["lon"])
        if not dados:
            continue
        
        dados["cidade"] = nome
        dados["codigo_ibge"] = codigo
        
        analise = analisar_clima(dados, clim.get(codigo, {}))
        if analise:
            analises.append(analise)
        
        time.sleep(0.3)
    
    duracao = (time.time() - inicio) / 60
    log(f"\n✅ {len(analises)} municípios em {duracao:.1f} min")
    
    cache = salvar_cache(analises)
    log(f"💾 CACHE: {cache['status_geral']}")
    log(f"   Anomalias clima: {cache['anomalias_clima']}")
    log(f"   Tempestades: {cache['tempestades_severas']}")
    
    arq = gerar_relatorio(analises)
    log(f"📄 Relatório: {arq}")
    
    # Exibir alertas no terminal
    print()
    if cache["cidades_tempestade"]:
        print("⛈️  TEMPESTADES SEVERAS:")
        for a in cache["cidades_tempestade"][:15]:
            print(f"  {a['cidade']:<25} {a['status_tempestade']}")
            for alerta in a["alertas_tempestade"][:2]:
                print(f"      → {alerta}")
    else:
        print("✅ Sem tempestades severas detectadas")

if __name__ == "__main__":
    main()
