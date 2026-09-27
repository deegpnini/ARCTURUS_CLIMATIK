#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — MÓDULO INMET HISTÓRICO
# ============================================================

import os
import io
import zipfile
import urllib.request
import csv
from pathlib import Path
from datetime import datetime

BASE = Path.home() / "ARCTURUS_CLIMATIK"
DIRS = {
    "bronze": BASE / "dados" / "bronze" / "inmet",
    "silver": BASE / "dados" / "silver",
    "climatologia": BASE / "climatologia",
    "logs": BASE / "logs",
}
for d in DIRS.values():
    d.mkdir(parents=True, exist_ok=True)

ANOS = [2020, 2021, 2022, 2023, 2024, 2025]
UF_ALVO = "SC"
MES_CLIMATOLOGIA = 9
URL_TEMPLATE = "https://portal.inmet.gov.br/uploads/dadoshistoricos/{ano}.zip"

def log(msg):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    with open(DIRS["logs"] / "inmet_historico.log", "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def baixar_zip(ano):
    destino = DIRS["bronze"] / f"{ano}.zip"
    if destino.exists():
        log(f"OK {ano}.zip ja existe ({destino.stat().st_size / 1e6:.1f} MB)")
        return destino
    url = URL_TEMPLATE.format(ano=ano)
    log(f"Baixando {ano}.zip")
    try:
        urllib.request.urlretrieve(url, destino)
        log(f"OK {ano}.zip baixado")
        return destino
    except Exception as e:
        log(f"ERRO ao baixar {ano}.zip: {e}")
        return None

def extrair_estacoes_sc(zip_path):
    """Extrai estacoes de SC sem pandas (apenas csv nativo)."""
    resultado = []
    header = None
    try:
        with zipfile.ZipFile(zip_path) as z:
            for nome in z.namelist():
                if not nome.upper().endswith(".CSV"):
                    continue
                partes = nome.upper().split("_")
                if len(partes) < 3 or partes[2] != UF_ALVO:
                    continue
                try:
                    with z.open(nome) as f:
                        conteudo = f.read().decode("latin-1")
                        linhas = conteudo.splitlines()
                        if len(linhas) < 10:
                            continue
                        # Cabecalho real esta na linha 9 (indice 8)
                        colunas = [c.strip() for c in linhas[8].split(";")]
                        if header is None:
                            header = colunas
                        for linha in linhas[9:]:
                            if not linha.strip():
                                continue
                            valores = linha.split(";")
                            if len(valores) != len(header):
                                continue
                            registro = dict(zip(header, valores))
                            registro["arquivo_origem"] = nome
                            resultado.append(registro)
                except Exception as e:
                    log(f"AVISO {nome}: {e}")
    except Exception as e:
        log(f"ERRO ao abrir {zip_path.name}: {e}")
    log(f"OK {len(resultado)} linhas extraidas de {zip_path.name}")
    return resultado, header

def limpar_registro(reg):
    """Limpa valores invalidos de um registro."""
    invalidos = {"-9999", "-9999.0", "null", "", " ", "9999.9"}
    limpo = {}
    for k, v in reg.items():
        v = v.strip() if isinstance(v, str) else v
        limpo[k] = None if v in invalidos else v
    return limpo

def parse_data(valor):
    if not valor:
        return None
    try:
        return datetime.strptime(valor, "%d/%m/%Y %H:%M")
    except Exception:
        return None

def gerar_climatologia_setembro(registros, header):
    """Calcula climatologia de setembro sem pandas."""
    # Localizar colunas de interesse
    mapa = {}
    for col in header:
        c = col.lower()
        if "data" in c and "hora" in c:
            mapa["data"] = col
        elif "temperatura" in c and "bulbo" not in c and "orvalho" not in c:
            if "max" in c:
                mapa["temp_max"] = col
            elif "min" in c:
                mapa["temp_min"] = col
            elif "media" in c:
                mapa["temp_media"] = col
        elif "umidade" in c:
            mapa["umidade"] = col
        elif "precipitacao" in c:
            mapa["precipitacao"] = col
        elif "vento" in c and "velocidade" in c:
            mapa["vento"] = col
    
    log(f"Colunas mapeadas: {list(mapa.keys())}")
    
    # Agregar por estacao
    estacoes = {}
    for reg in registros:
        data_str = reg.get(mapa.get("data", ""), "")
        dt = parse_data(data_str)
        if not dt or dt.month != MES_CLIMATOLOGIA:
            continue
        
        estacao = reg.get("arquivo_origem", "?").split("_")[3] if "_" in reg.get("arquivo_origem", "") else "?"
        
        if estacao not in estacoes:
            estacoes[estacao] = {
                "temp_media": [], "temp_min": [], "temp_max": [],
                "umidade": [], "precipitacao": []
            }
        
        for campo in ["temp_media", "temp_min", "temp_max", "umidade", "precipitacao"]:
            col = mapa.get(campo)
            if not col:
                continue
            val = reg.get(col)
            if val is None:
                continue
            try:
                estacoes[estacao][campo].append(float(val))
            except Exception:
                continue
    
    # Calcular medias
    resumo = []
    for est, dados in estacoes.items():
        linha = {"estacao": est, "n_amostras": len(dados["temp_media"])}
        for campo, valores in dados.items():
            if valores:
                linha[f"{campo}_media"] = round(sum(valores) / len(valores), 2)
                if campo == "temp_min":
                    linha["temp_min_absoluta"] = min(valores)
                if campo == "temp_max":
                    linha["temp_max_absoluta"] = max(valores)
            else:
                linha[f"{campo}_media"] = None
        resumo.append(linha)
    
    return resumo

def salvar_csv(caminho, linhas, colunas=None):
    if not linhas:
        return
    if colunas is None:
        colunas = list(linhas[0].keys())
    with open(caminho, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=colunas)
        w.writeheader()
        for linha in linhas:
            w.writerow({k: linha.get(k) for k in colunas})

def main():
    log("=" * 60)
    log("ARCTURUS — INMET HISTORICO")
    log("=" * 60)
    
    todos = []
    header_global = None
    
    for ano in ANOS:
        zip_path = baixar_zip(ano)
        if zip_path is None:
            continue
        registros, header = extrair_estacoes_sc(zip_path)
        if not registros:
            continue
        if header_global is None:
            header_global = header
        for reg in registros:
            todos.append(limpar_registro(reg))
    
    if not todos:
        log("Nenhum dado disponivel")
        return
    
    log(f"Total consolidado: {len(todos)} linhas")
    
    # Salvar silver (CSV simples)
    saida_silver = DIRS["silver"] / "inmet_sc_horario.csv"
    salvar_csv(saida_silver, todos)
    log(f"Salvo: {saida_silver}")
    
    # Climatologia de setembro
    clim = gerar_climatologia_setembro(todos, header_global)
    if clim:
        saida_clim = DIRS["climatologia"] / "sc_setembro.csv"
        salvar_csv(saida_clim, clim)
        log(f"Climatologia salva: {saida_clim}")
        print()
        print("PREVIA DA CLIMATOLOGIA DE SETEMBRO:")
        for linha in clim[:10]:
            print(linha)
    
    log("Pipeline concluido")

if __name__ == "__main__":
    main()
