import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # Para rodar sem interface gráfica
import matplotlib.pyplot as plt
from pathlib import Path
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
DB_PATH = BASE / "data" / "arcturus.db"
CSV_PATH = BASE / "resultados" / "historico_previsoes.csv"
OUT_PNG = BASE / "resultados" / "analise_cota.png"

# 1. Lê o SQLite
conn = sqlite3.connect(DB_PATH)
df_sql = pd.read_sql_query("SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, regime FROM leituras", conn)
conn.close()
df_sql['timestamp'] = pd.to_datetime(df_sql['timestamp'])
df_sql = df_sql.sort_values('timestamp')

# 2. Lê o CSV (caso o SQLite tenha lacunas)
df_csv = pd.read_csv(CSV_PATH)
df_csv['timestamp_execucao'] = pd.to_datetime(df_csv['timestamp_execucao'])
df_csv = df_csv.rename(columns={'timestamp_execucao': 'timestamp', 'cota_atual_cm': 'cota_cm'})
df_csv = df_csv[['timestamp', 'cota_cm']].dropna()
df_csv = df_csv.sort_values('timestamp')

# 3. Estatística básica (numpy)
cotas = df_sql['cota_cm'].dropna().values
print("=== ESTATÍSTICA DA COTA (SQLite) ===")
print(f"Total de leituras: {len(cotas)}")
print(f"Média: {np.mean(cotas):.2f} cm")
print(f"Desvio padrão: {np.std(cotas):.2f} cm")
print(f"Mínimo: {np.min(cotas):.2f} cm")
print(f"Máximo: {np.max(cotas):.2f} cm")
print(f"Mediana: {np.median(cotas):.2f} cm")

# 4. Plota o gráfico (matplotlib)
fig, ax = plt.subplots(figsize=(12, 6))
ax.plot(df_sql['timestamp'], df_sql['cota_cm'], marker='o', linestyle='-', color='#00d2ff', label='Cota (SQLite)')
ax.plot(df_csv['timestamp'], df_csv['cota_cm'], marker='x', linestyle='--', color='#ff6b6b', label='Cota (CSV)', alpha=0.7)
ax.set_title('Análise Hidrológica — Cota do Rio Tubarão (ERAB)')
ax.set_xlabel('Data / Hora')
ax.set_ylabel('Cota (cm)')
ax.grid(True, alpha=0.3)
ax.legend()
plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=100)
print(f"\n✅ Gráfico salvo em: {OUT_PNG}")

# 5. Estatística da variação (Vz) — só se existir
if 'vz_cm_h' in df_sql.columns and df_sql['vz_cm_h'].notna().any():
    vzs = df_sql['vz_cm_h'].dropna().values
    print("\n=== ESTATÍSTICA DO VZ (SQLite) ===")
    print(f"Média: {np.mean(vzs):.2f} cm/h")
    print(f"Desvio padrão: {np.std(vzs):.2f} cm/h")
    print(f"Mínimo: {np.min(vzs):.2f} cm/h")
    print(f"Máximo: {np.max(vzs):.2f} cm/h")

# 6. Estatística do Az — só se existir
if 'az_cm_h2' in df_sql.columns and df_sql['az_cm_h2'].notna().any():
    azs = df_sql['az_cm_h2'].dropna().values
    print("\n=== ESTATÍSTICA DO AZ (SQLite) ===")
    print(f"Média: {np.mean(azs):.2f} cm/h²")
    print(f"Desvio padrão: {np.std(azs):.2f} cm/h²")
    print(f"Mínimo: {np.min(azs):.2f} cm/h²")
    print(f"Máximo: {np.max(azs):.2f} cm/h²")
