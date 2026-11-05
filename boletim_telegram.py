#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boletim informativo do rio para o Telegram (a cada 30 min)."""

import json
import os
import requests
import psycopg2
from datetime import datetime
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DB_URL = os.environ.get("DATABASE_URL", "postgresql:///arcturus")

# Carrega token/chat do .env
env_file = BASE / ".env"
if env_file.exists():
    with open(env_file) as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k] = v.strip('"').strip("'")

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

if not TOKEN or not CHAT_ID:
    print("[ERRO] TELEGRAM_TOKEN/TELEGRAM_CHAT_ID não definidos no .env")
    exit(1)

# --- 1) Cota atual e anterior (últimas 2 leituras) ---
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT timestamp, cota_cm, qc FROM leituras
    WHERE cota_cm IS NOT NULL
    ORDER BY timestamp DESC LIMIT 2
""")
rows = cur.fetchall()
if not rows:
    print("[ERRO] Sem leituras no banco")
    exit(1)

ts_atual, cota_atual, qc_atual = rows[0]
cota_anterior = rows[1][1] if len(rows) > 1 else None
variacao = (cota_atual - cota_anterior) if cota_anterior is not None else 0

# --- 2) Previsão (última predição) ---
cur.execute("""
    SELECT horizonte, y_score FROM predicoes_shadow
    WHERE timestamp > NOW() - INTERVAL '20 minutes'
      AND stale = false
    ORDER BY timestamp DESC, horizonte
    LIMIT 3
""")
previsoes = {h: y for h, y in cur.fetchall()}
cur.close()
conn.close()

# --- 3) Probabilidade (simulação) ---
prob = 0
sim_file = BASE / "data" / "simulacao_probabilidade_atual.json"
if sim_file.exists():
    with open(sim_file) as f:
        sim = json.load(f)
        prob = sim.get("prob_media", 0) * 100

# --- 4) Chuva (últimas 24h na bacia) ---
chuva_24h = 0
chuva_file = BASE / "data" / "chuva_bacia_openmeteo.csv"
if chuva_file.exists():
    try:
        df = pd.read_csv(chuva_file, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df.loc[~df.index.isna()].sort_index()
        ultimas_24h = df[df.index > (datetime.now() - pd.Timedelta(hours=24))]
        if len(ultimas_24h) > 0:
            chuva_24h = ultimas_24h.mean(axis=1).sum()
    except Exception as e:
        print(f"[AVISO] Erro ao ler chuva: {e}")

# --- 5) Formata a mensagem ---
def cor_cota(cota):
    if cota < 50: return "🔵 Baixo"
    elif cota < 250: return "🟢 Normal"
    elif cota < 350: return "🟡 Atenção"
    elif cota < 600: return "🟠 Alerta"
    else: return "🔴 Emergência"

def seta_variacao(v):
    if v > 0.5: return f"⬆️ +{v:.1f} cm"
    elif v < -0.5: return f"⬇️ {v:.1f} cm"
    else: return "➡️ estável"

msg = f"""
🌊 *ARCTURUS — Boletim do Rio Tubarão*
_{ts_atual.strftime('%d/%m/%Y %H:%M')}_

*Cota atual:* {cota_atual:.1f} cm ({cor_cota(cota_atual)})
*Variação:* {seta_variacao(variacao)} desde a última leitura

*Previsão:*
• 1h: {previsoes.get('1h', 0):+.2f} cm
• 3h: {previsoes.get('3h', 0):+.2f} cm
• 6h: {previsoes.get('6h', 0):+.2f} cm

*Chuva acumulada 24h:* {chuva_24h:.1f} mm
*Probabilidade de cheia:* {prob:.2f}%

_Modo sombra. Não é alerta de perigo._
"""

# --- 6) Envia para o Telegram ---
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
resp = requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"})
if resp.status_code == 200:
    print(f"[OK] Boletim enviado às {datetime.now().strftime('%H:%M')}")
else:
    print(f"[ERRO] Telegram retornou {resp.status_code}: {resp.text}")
