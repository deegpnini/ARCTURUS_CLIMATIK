#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Boletim informativo do rio para o Telegram (com proveniência e telemetria real Defesa Civil SC)."""

import json
import os
import sys
import requests
import psycopg2
from datetime import datetime, timedelta
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parent
DB_URL = os.environ.get("DATABASE_URL", "postgresql:///arcturus")

# Carrega token/chat do .env
env_file = BASE / ".env"
if env_file.exists():
    with open(env_file, encoding="utf-8") as f:
        for line in f:
            if "=" in line and not line.startswith("#"):
                k, v = line.strip().split("=", 1)
                os.environ[k] = v.strip('"').strip("'")

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
DRY_RUN = "--dry-run" in sys.argv

if not DRY_RUN and (not TOKEN or not CHAT_ID):
    print("[ERRO] TELEGRAM_TOKEN/TELEGRAM_CHAT_ID não definidos no .env")
    sys.exit(1)

# --- 1) Cota atual, anterior e taxa horária (vz) ---
conn = psycopg2.connect(DB_URL)
cur = conn.cursor()
cur.execute("""
    SELECT timestamp, cota_cm, qc, chuva_pior_caso_mm FROM leituras
    WHERE cota_cm IS NOT NULL
    ORDER BY timestamp DESC LIMIT 2
""")
rows = cur.fetchall()
if not rows:
    print("[ERRO] Sem leituras no banco")
    sys.exit(1)

ts_atual, cota_atual, qc_atual, chuva_db_atual = rows[0]
cota_anterior = rows[1][1] if len(rows) > 1 else None
ts_anterior = rows[1][0] if len(rows) > 1 else None
variacao = (cota_atual - cota_anterior) if cota_anterior is not None else 0.0

if ts_anterior is not None and cota_anterior is not None:
    dt_horas = max((ts_atual - ts_anterior).total_seconds() / 3600.0, 1.0 / 60.0)
    vz_h = variacao / dt_horas
else:
    vz_h = 0.0

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
prob = 0.0
sim_file = BASE / "data" / "simulacao_probabilidade_atual.json"
if sim_file.exists():
    try:
        with open(sim_file, encoding="utf-8") as f:
            sim = json.load(f)
            prob = sim.get("prob_media", 0.0) * 100.0
    except Exception as e:
        print(f"[AVISO] Erro ao ler simulação: {e}")

# --- 4) Chuva acumulada 24h com Proveniência (Defesa Civil SC + Open-Meteo) ---
chuva_24h = 0.0
fonte_chuva_label = "Open-Meteo"
prov_file = BASE / "data" / "proveniencia_observacoes.jsonl"
leu_proveniencia = False

if prov_file.exists():
    try:
        linhas_prov = [l.strip() for l in prov_file.read_text(encoding="utf-8").splitlines() if l.strip()]
        if linhas_prov:
            ult_prov = json.loads(linhas_prov[-1])
            ts_ciclo = datetime.fromisoformat(ult_prov["ts_ciclo_gravacao"])
            if (datetime.now() - ts_ciclo).total_seconds() <= 7200:
                val = ult_prov.get("estimativa_conservadora_24h_mm")
                if val is not None:
                    chuva_24h = float(val)
                    dom = ult_prov.get("fonte_dominante", "")
                    if "DEFESA_CIVIL" in dom:
                        fonte_chuva_label = "Defesa Civil SC — Telemetria"
                    elif "OPEN_METEO" in dom:
                        fonte_chuva_label = "Open-Meteo — Grade Bacia"
                    leu_proveniencia = True
    except Exception as e:
        print(f"[AVISO] Erro ao ler proveniencia_observacoes.jsonl: {e}")

if not leu_proveniencia and chuva_db_atual is not None:
    chuva_24h = float(chuva_db_atual)
    fonte_chuva_label = "PostgreSQL — Fusão Conservadora"
    leu_proveniencia = True

if not leu_proveniencia:
    chuva_file = BASE / "data" / "chuva_bacia_openmeteo.csv"
    if chuva_file.exists():
        try:
            df = pd.read_csv(chuva_file, index_col=0, parse_dates=True)
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df.loc[~df.index.isna()].sort_index()
            ultimas_24h = df[df.index > (datetime.now() - pd.Timedelta(hours=24))]
            if len(ultimas_24h) > 0:
                chuva_24h = float(ultimas_24h.mean(axis=1).sum())
        except Exception as e:
            print(f"[AVISO] Erro ao ler chuva CSV: {e}")

# --- 4.1) Telemetria Real das Estações (Defesa Civil SC) ---
telemetria_texto = ""
dc_file = BASE / "data" / "chuva_defesacivil_realtime.json"
if dc_file.exists():
    try:
        dc_dados = json.loads(dc_file.read_text(encoding="utf-8"))
        ts_coleta_str = dc_dados.get("timestamp_coleta")
        dc_valido = True
        hora_coleta_fmt = ""
        if ts_coleta_str:
            dt_col = datetime.fromisoformat(ts_coleta_str)
            if (datetime.now() - dt_col).total_seconds() > 7200:
                dc_valido = False
            else:
                hora_coleta_fmt = f" _({dt_col.strftime('%H:%M')})_"

        estacoes = dc_dados.get("estacoes", [])
        if dc_valido and estacoes:
            estacoes_ord = sorted(
                estacoes,
                key=lambda x: (
                    x.get("chuva_24h_mm") if x.get("chuva_24h_mm") is not None else -1.0,
                    x.get("chuva_1h_mm") if x.get("chuva_1h_mm") is not None else -1.0,
                ),
                reverse=True,
            )
            linhas_est = []
            for est in estacoes_ord:
                trecho = est.get("trecho_bacia") or est.get("nome") or est.get("codigo")
                c1 = est.get("chuva_1h_mm")
                c24 = est.get("chuva_24h_mm")
                rio = est.get("rio_m")
                partes = []
                if c1 is not None:
                    partes.append(f"{c1:.1f} mm (1h)")
                if c24 is not None:
                    partes.append(f"{c24:.1f} mm (24h)")
                if rio is not None:
                    partes.append(f"Rio: {rio:.2f} m")
                if partes:
                    linhas_est.append(f"• *{trecho}:* " + " | ".join(partes))
            if linhas_est:
                telemetria_texto = f"\n📡 *Telemetria Real — Defesa Civil SC*{hora_coleta_fmt}\n" + "\n".join(linhas_est) + "\n"
    except Exception as e:
        print(f"[AVISO] Erro ao ler telemetria Defesa Civil SC: {e}")

# --- 5) Previsão do tempo (por dia, com data explícita) ---
tempo_texto = ""
tempo_file = BASE / "data" / "previsao_tempo.json"
if tempo_file.exists():
    try:
        with open(tempo_file, "r", encoding="utf-8") as f:
            tempo = json.load(f)

        tempo_texto = "\n🌤️ *Previsão do Tempo — Bacia do Rio Tubarão*\n"
        hoje = datetime.now()
        datas = [
            ("hoje", hoje.strftime("%d/%m")),
            ("amanha", (hoje + timedelta(days=1)).strftime("%d/%m")),
            ("depois_amanha", (hoje + timedelta(days=2)).strftime("%d/%m")),
        ]

        tempo_texto += "\n*🏔️ Cabeceira (Serra):*\n"
        for cidade in ["lauro_muller", "orleans", "anitapolis", "sao_bonifacio"]:
            if cidade in tempo:
                t = tempo[cidade]
                nome = cidade.replace("_", " ").title()
                tempo_texto += f"*{nome}:*\n"
                for chave, data in datas:
                    if chave in t:
                        d = t[chave]
                        tempo_texto += f"  {data}: {d['temp_min']:.0f}°C a {d['temp_max']:.0f}°C | Chuva: {d['chuva']:.1f} mm\n"

        tempo_texto += "\n*🌳 Médio Curso:*\n"
        for cidade in ["braco_do_norte", "sao_ludgero", "pedras_grandes", "armazem", "gravatal"]:
            if cidade in tempo:
                t = tempo[cidade]
                nome = cidade.replace("_", " ").title()
                tempo_texto += f"*{nome}:*\n"
                for chave, data in datas:
                    if chave in t:
                        d = t[chave]
                        tempo_texto += f"  {data}: {d['temp_min']:.0f}°C a {d['temp_max']:.0f}°C | Chuva: {d['chuva']:.1f} mm\n"

        tempo_texto += "\n*🌊 Foz / Litoral:*\n"
        for cidade in ["tubarao", "capivari_de_baixo", "jaguaruna", "laguna"]:
            if cidade in tempo:
                t = tempo[cidade]
                nome = cidade.replace("_", " ").title()
                tempo_texto += f"*{nome}:*\n"
                for chave, data in datas:
                    if chave in t:
                        d = t[chave]
                        tempo_texto += f"  {data}: {d['temp_min']:.0f}°C a {d['temp_max']:.0f}°C | Chuva: {d['chuva']:.1f} mm\n"

        total_chuva = 0.0
        for cidade, dias in tempo.items():
            for chave in ["hoje", "amanha", "depois_amanha"]:
                if chave in dias:
                    total_chuva += dias[chave]["chuva"]
        tempo_texto += f"\n*Chuva total prevista na bacia (3 dias):* {total_chuva:.1f} mm\n"

    except Exception as e:
        print(f"[AVISO] Erro ao ler previsão do tempo: {e}")

# --- 6) Classificação de estado e formatação ---
def classificar_estado_boletim(cota: float, chuva24: float, taxa_vz: float) -> str:
    if cota > 300 or chuva24 > 50 or taxa_vz > 10:
        motivos = []
        if cota > 300: motivos.append("Cota > 300 cm")
        if chuva24 > 50: motivos.append(f"Chuva 24h: {chuva24:.1f} mm")
        if taxa_vz > 10: motivos.append(f"Subida: {taxa_vz:.1f} cm/h")
        return f"🔴 Extremo ({', '.join(motivos)})"
    if cota > 200 or chuva24 > 20 or taxa_vz > 5:
        motivos = []
        if cota > 200: motivos.append("Cota > 200 cm")
        if chuva24 > 20: motivos.append(f"Chuva 24h: {chuva24:.1f} mm")
        if taxa_vz > 5: motivos.append(f"Subida: {taxa_vz:.1f} cm/h")
        return f"🟠 Alerta ({', '.join(motivos)})"
    if cota > 100 or chuva24 > 5 or taxa_vz > 1:
        motivos = []
        if cota > 100: motivos.append("Cota > 100 cm")
        if chuva24 > 5: motivos.append(f"Chuva 24h: {chuva24:.1f} mm")
        if taxa_vz > 1: motivos.append(f"Subida: {taxa_vz:.1f} cm/h")
        return f"🟡 Atenção ({', '.join(motivos)})"
    if cota < 50:
        return "🔵 Baixo"
    return "🟢 Normal"

def seta_variacao(v: float) -> str:
    if v > 0.5:
        return f"⬆️ +{v:.1f} cm"
    elif v < -0.5:
        return f"⬇️ {v:.1f} cm"
    return "➡️ estável"

estado_label = classificar_estado_boletim(cota_atual, chuva_24h, vz_h)

msg = f"""🌊 *ARCTURUS — Boletim do Rio Tubarão*
_{ts_atual.strftime('%d/%m/%Y %H:%M')}_

*Estado hidrometeorológico:* {estado_label}
*Cota atual (Tubarão):* {cota_atual:.1f} cm
*Variação:* {seta_variacao(variacao)} desde a última leitura

*Previsão:*
• 1h: {previsoes.get('1h', 0):+.2f} cm
• 3h: {previsoes.get('3h', 0):+.2f} cm
• 6h: {previsoes.get('6h', 0):+.2f} cm

*Chuva acumulada 24h:* {chuva_24h:.1f} mm _({fonte_chuva_label})_
*Probabilidade de cheia:* {prob:.2f}%
{telemetria_texto}{tempo_texto}
_Modo sombra. Não é alerta de perigo._"""

if DRY_RUN:
    print("=== DRY-RUN: MENSAGEM QUE SERÁ ENVIADA AO TELEGRAM ===")
    print(msg)
    sys.exit(0)

# --- 7) Envia para o Telegram ---
url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
resp = requests.post(url, data={"chat_id": CHAT_ID, "text": msg, "parse_mode": "Markdown"}, timeout=20)
if resp.status_code == 200:
    print(f"[OK] Boletim enviado às {datetime.now().strftime('%H:%M')}")
else:
    print(f"[ERRO] Telegram retornou {resp.status_code}: {resp.text}")
