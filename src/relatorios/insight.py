"""
ARCTURUS CLIMATIK — insight.py
Gera relatorio tecnico + publico de previsao hidrologica.

Modos:
- retrospectivo: analisa evento historico
- ao_vivo: analisa leitura atual (so se passar bloqueios de seguranca)

Bloqueios:
- estacao desatualizada (> 3h)
- modelo com hash divergente
- features faltando
- integridade violada
"""
import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from datetime import datetime, timedelta

import numpy as np
import pandas as pd
import lightgbm as lgb

# ============================================================
# PATHS
# ============================================================
ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)

DATA = ROOT / "data"
MODELOS = ROOT / "modelos"
RES = ROOT / "resultados"
INSIGHTS = RES / "insights"
INSIGHTS.mkdir(parents=True, exist_ok=True)

TEMPLATES = ROOT / "src" / "relatorios" / "templates"

# ============================================================
# UTILS
# ============================================================
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

def carregar_manifesto():
    path = MODELOS / "manifesto_producao.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)

def validar_modelos(manifesto):
    """Verifica hash dos 3 modelos. Retorna (ok, problemas)."""
    problemas = []
    for h, info in manifesto["horizontes"].items():
        path = MODELOS / info["arquivo"]
        if not path.exists():
            problemas.append(f"{h}: arquivo ausente {info['arquivo']}")
            continue
        hash_atual = sha256(path)
        if hash_atual != info["sha256_modelo"]:
            problemas.append(f"{h}: hash divergente ({hash_atual[:16]} != {info['sha256_modelo'][:16]})")
    return len(problemas) == 0, problemas

# ============================================================
# COLETA DE DADOS
# ============================================================
def carregar_telemetria_cache():
    """Carrega a telemetria 2026 do cache local."""
    path = DATA / "telemetria_84580000_2026.json"
    if not path.exists():
        return None, "telemetria cache nao encontrado"
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    return d.get("items") or [], None

def extrair_leituras(items):
    """Extrai lista de (timestamp, cota, chuva) ordenada por timestamp."""
    out = []
    for it in items:
        ts = it.get("Data_Hora_Medicao")
        if not ts:
            continue
        cota = it.get("Cota_Adotada")
        chuva = it.get("Chuva_Adotada")
        try:
            cota_f = float(str(cota).replace(",", ".")) if cota not in (None, "") else None
        except:
            cota_f = None
        try:
            chuva_f = float(str(chuva).replace(",", ".")) if chuva not in (None, "") else None
        except:
            chuva_f = None
        try:
            ts_dt = pd.to_datetime(ts)
        except:
            continue
        out.append({"ts": ts_dt, "cota": cota_f, "chuva": chuva_f})
    out.sort(key=lambda x: x["ts"])
    return out

def determinar_modo(leituras):
    """Define se esta ao vivo ou retrospectivo. Retorna (modo, ultima_leitura, idade_h)."""
    if not leituras:
        return "sem_dados", None, None
    ultima = leituras[-1]["ts"]
    agora = pd.Timestamp.now()
    idade_h = (agora - ultima).total_seconds() / 3600
    if idade_h < 3:
        return "ao_vivo", ultima, idade_h
    return "retrospectivo", ultima, idade_h

# ============================================================
# MAIN
# ============================================================
def main():
    parser = argparse.ArgumentParser(description="ARCTURUS insight.py")
    parser.add_argument("--modo", choices=["auto", "retrospectivo", "ao_vivo"], default="auto",
                        help="Modo de operacao (auto = detecta)")
    parser.add_argument("--data", help="Data de referencia (YYYY-MM-DD HH:MM) para modo retrospectivo")
    args = parser.parse_args()

    print("=" * 70)
    print("  ARCTURUS CLIMATIK — insight.py")
    print(f"  Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # 1. Carrega manifesto
    print("[1] Carregando manifesto de producao...")
    manifesto = carregar_manifesto()
    print(f"    Projeto: {manifesto['projeto']}")
    print(f"    Versao:  {manifesto['versao']}")
    print(f"    Status:  {manifesto['status']}")
    print()

    # 2. Valida modelos
    print("[2] Validando integridade dos modelos...")
    ok, problemas = validar_modelos(manifesto)
    if ok:
        print("    [OK] 3 modelos com hash correto")
    else:
        print("    [FALHA] problemas detectados:")
        for p in problemas:
            print(f"      - {p}")
        print()
        print("BLOQUEIO: modelos com hash divergente. Abortando.")
        sys.exit(1)
    print()

    # 3. Carrega telemetria
    print("[3] Carregando telemetria do cache...")
    items, erro = carregar_telemetria_cache()
    if erro:
        print(f"    [FALHA] {erro}")
        sys.exit(1)
    leituras = extrair_leituras(items)
    print(f"    Total: {len(leituras)} leituras")
    print()

    # 4. Determina modo
    print("[4] Determinando modo de operacao...")
    modo_detectado, ultima, idade_h = determinar_modo(leituras)
    print(f"    Ultima leitura: {ultima}")
    print(f"    Idade: {idade_h:.1f}h")
    print(f"    Modo detectado: {modo_detectado}")
    print()

    # 5. Bloqueio de seguranca
    if modo_detectado != "ao_vivo":
        print("[5] BLOQUEIO DE SEGURANCA")
        print(f"    Estacao desatualizada ({idade_h:.1f}h sem leitura).")
        print(f"    Nao e' possivel emitir previsao ao vivo.")
        print(f"    Sugestao: usar --modo retrospectivo --data 'YYYY-MM-DD HH:MM'")
        print()
        if args.modo != "retrospectivo":
            print("Saindo sem gerar relatorio. Use --modo retrospectivo para analise historica.")
            sys.exit(0)

    print("[5] Modo retrospectivo sera usado.")
    print()

    print("=" * 70)
    print("  PARTE 1 CONCLUIDA")
    print("  (proxima parte: reconstruir features + prever)")
    print("=" * 70)

if __name__ == "__main__":
    main()
