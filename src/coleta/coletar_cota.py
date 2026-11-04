#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Coleta de cota com fallback em cascata: ERAB (P0) → ANA (P1) → Cache (P2)."""

import json
import logging
import sys
from datetime import datetime, date, timedelta
from pathlib import Path

import requests
import psycopg2

# Adiciona a raiz do projeto ao sys.path (para importar src.*)
BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))
LOG = logging.getLogger("coletar_cota")
CACHE_FILE = BASE / "data" / "ultima_cota_valida.json"

# --- P0: ERAB (fonte primária) ---
def coletar_erab():
    """Tenta o scraper da ERAB (Tubarão Saneamento)."""
    try:
        from src.relatorios.coletar_tubarao_saneamento import coletar_cota
        coletar_cota()
        return True
    except Exception as e:
        LOG.warning("ERAB falhou: %s", e)
        return False

# --- P1: ANA (fallback) ---
def coletar_ana(codigo="84580000"):
    """Tenta a API nova da ANA com os parâmetros corretos (com espaços)."""
    try:
        from src.coleta.ana_auth import get_token
        token = get_token()
        headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
        url = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"
        params = {
            "Código da Estação": codigo,
            "Tipo Filtro Data": "DATA_LEITURA",
            "Range Intervalo de busca": "HORA_24",
        }
        resp = requests.get(url, params=params, headers=headers, timeout=60)
        if resp.status_code == 200:
            dados = resp.json()
            items = dados.get("items", [])
            if items:
                # Pega a última leitura (a mais recente)
                ultima = items[-1]
                cota_cm = ultima.get("Cota", ultima.get("Nivel", None))
                if cota_cm is not None:
                    # Salva no cache
                    cache = {"cota_cm": cota_cm, "timestamp": datetime.now().isoformat(), "fonte": "ANA"}
                    CACHE_FILE.write_text(json.dumps(cache), encoding="utf-8")
                    LOG.info("ANA: cota %.1f cm (fonte: ANA)", cota_cm)
                    return True
        LOG.warning("ANA: sem dados (HTTP %s)", resp.status_code)
        return False
    except Exception as e:
        LOG.warning("ANA falhou: %s", e)
        return False

# --- P2: Cache (último recurso) ---
def usar_cache():
    """Usa a última cota válida salva em cache."""
    if CACHE_FILE.exists():
        try:
            cache = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            LOG.warning("Usando cache: cota %.1f cm (de %s)", cache["cota_cm"], cache["timestamp"])
            return cache["cota_cm"]
        except Exception as e:
            LOG.error("Cache corrompido: %s", e)
    LOG.error("Sem cota disponível (ERAB, ANA e cache falharam)")
    return None

# --- Orquestrador ---
def coletar_cota():
    """Executa o fallback em cascata."""
    if coletar_erab():
        LOG.info("Cota coletada da ERAB (P0)")
        return True
    LOG.warning("ERAB falhou. Tentando ANA (P1)...")
    if coletar_ana():
        LOG.info("Cota coletada da ANA (P1)")
        return True
    LOG.warning("ANA falhou. Usando cache (P2)...")
    cota = usar_cache()
    return cota is not None

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    coletar_cota()
