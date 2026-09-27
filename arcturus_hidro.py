#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — MÓDULO HIDROLÓGICO v1.4
# Defesa Civil SC + Epagri/Ciram (sem token)
# ============================================================

import os
import ssl
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path
import certifi

BASE = Path.home() / "ARCTURUS_CLIMATIK"
CACHE_FILE = BASE / "cache" / "arcturus_hidro.json"
LOG_FILE = BASE / "logs" / "hidro.log"

CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

def log(msg):
    ts = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    linha = f"[{ts}] {msg}"
    print(linha)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(linha + "\n")

def fetch(url, timeout=15):
    ctx = ssl.create_default_context(cafile=certifi.where())
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) ARCTURUS/1.4"
    })
    try:
        with urllib.request.urlopen(req, context=ctx, timeout=timeout) as r:
            return r.read().decode("utf-8", errors="ignore")
    except Exception as e:
        log(f"   ⚠️ {url[:60]}: {str(e)[:80]}")
        return None

# ============================================================
# FONTE 1: DEFESA CIVIL SC — Alertas Oficiais
# ============================================================
def consultar_defesa_civil_sc():
    """Extrai alertas hidrológicos do portal da Defesa Civil SC."""
    resultado = {
        "fonte": "Defesa Civil SC",
        "url": "https://defesacivil.sc.gov.br/",
        "alertas": [],
        "status": "⚪ SEM DADOS",
        "confiavel": False,
    }
    
    html = fetch(resultado["url"])
    if not html:
        return resultado
    
    # Procurar menções a rios
    matches = re.findall(
        r'(rio\s+[\w\-áéíóúç]+(?:[\s-]+[\w\-áéíóúç]+)?)[^.]{0,200}(?:alerta|cheia|cota|nível|nivel)[^.]{0,200}',
        html, re.IGNORECASE
    )
    
    if matches:
        resultado["status"] = "🟢 MONITORADO"
        resultado["confiavel"] = True
        for m in matches[:5]:
            resultado["alertas"].append(m.strip()[:200])
    
    return resultado

# ============================================================
# FONTE 2: EPAGRI/CIRAM — Monitoramento
# ============================================================
def consultar_epagri_ciram():
    resultado = {
        "fonte": "Epagri/Ciram",
        "url": "https://ciram.epagri.sc.gov.br/",
        "status": "⚪ SEM DADOS",
        "confiavel": False,
    }
    
    html = fetch(resultado["url"])
    if html and len(html) > 1000:
        resultado["status"] = "🟢 MONITORADO"
        resultado["confiavel"] = True
    
    return resultado

# ============================================================
# MAIN
# ============================================================
def main():
    log("=" * 60)
    log("💧 ARCTURUS — VARREDURA HIDROLÓGICA v1.4")
    log("=" * 60)
    
    log("📡 Consultando Defesa Civil SC...")
    r1 = consultar_defesa_civil_sc()
    log(f"   → {r1['status']} | Alertas: {len(r1['alertas'])}")
    
    log("📡 Consultando Epagri/Ciram...")
    r2 = consultar_epagri_ciram()
    log(f"   → {r2['status']}")
    
    payload = {
        "ultima_atualizacao": datetime.now().strftime("%d/%m/%Y %H:%M"),
        "defesa_civil": r1,
        "epagri": r2,
        "nota": "Aguardando token ANA para cotas exatas. Fontes monitoradas como fallback.",
    }
    
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    log(f"✅ Cache: {CACHE_FILE}")
    log("=" * 60)
    
    print()
    print("📊 RESULTADO:")
    print(f"  Defesa Civil SC: {r1['status']}")
    if r1['alertas']:
        for a in r1['alertas'][:3]:
            print(f"    • {a[:100]}")
    print(f"  Epagri/Ciram: {r2['status']}")

if __name__ == "__main__":
    main()
