#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Monitora a cota a cada 15 min e registra a subida (para medir o lag)."""
import time
import psycopg2
import pandas as pd
from datetime import datetime
from pathlib import Path

DB_URL = "postgresql:///arcturus"
OUT = Path("resultados/monitor_lag.csv")

def ler_cota():
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    cur.execute("SELECT timestamp, cota_cm, qc FROM leituras ORDER BY id DESC LIMIT 1;")
    row = cur.fetchone()
    cur.close()
    conn.close()
    return row

print("=" * 60)
print("MONITOR DE LAG — ARCTURUS")
print("Cada linha é uma leitura. O tempo entre a chuva e a subida é o lag.")
print("Ctrl+C para parar.")
print("=" * 60)

# Cria o CSV (se não existir)
if not OUT.exists():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w") as f:
        f.write("timestamp_leitura,cota_cm,qc,hora_coleta\n")

# Loop de 15 em 15 min (48 horas = 192 ciclos)
for i in range(192):
    row = ler_cota()
    if row:
        ts, cota, qc = row
        agora = datetime.now().strftime("%Y-%m-%d %H:%M")
        print(f"[{agora}] Cota: {cota:.0f} cm ({qc})")
        with open(OUT, "a") as f:
            f.write(f"{ts},{cota},{qc},{agora}\n")
    time.sleep(900)  # 15 minutos
