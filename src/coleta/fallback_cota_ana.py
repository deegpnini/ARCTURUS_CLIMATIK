#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fallback de cota: tenta a ANA se a ERAB falhar."""

import os
import requests
import json
from datetime import datetime, timedelta
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent.parent
ANA_TOKEN = os.environ.get("ANA_TOKEN")  # Token do HidroWeb

# Estação da ANA em Tubarão (Ponte do Quartel ou Rio do Pouso)
ESTACAO_ANA = "84580000"  # Código da estação (ajustar se necessário)

def buscar_cota_ana():
    if not ANA_TOKEN:
        print("[AVISO] ANA_TOKEN não configurado. Fallback de cota desativado.")
        return None
    
    # Endpoint da ANA (exemplo, pode variar)
    url = f"https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetrica/{ESTACAO_ANA}"
    headers = {"Authorization": f"Bearer {ANA_TOKEN}"}
    
    try:
        resp = requests.get(url, headers=headers, timeout=30)
        if resp.status_code == 200:
            dados = resp.json()
            # Extrair a última cota (ajustar conforme o JSON da ANA)
            # Isso é um exemplo; o JSON da ANA tem estrutura própria.
            print(f"[ANA] Dados recebidos: {dados}")
            return dados
        else:
            print(f"[ANA] Erro {resp.status_code}")
            return None
    except Exception as e:
        print(f"[ANA] Falha: {e}")
        return None

if __name__ == "__main__":
    buscar_cota_ana()
