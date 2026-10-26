import sqlite3
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DB_PATH = BASE / "data" / "arcturus.db"
OUT_PNG = BASE / "resultados" / "analise_hidrologica_v2.png"

conn = sqlite3.connect(DB_PATH)
df = pd.read_sql_query("SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, regime FROM leituras ORDER BY timestamp", conn)
conn.close()
df['timestamp'] = pd.to_datetime(df['timestamp'])

fig, axes = plt.subplots(3, 1, figsize=(12, 10), sharex=True)

# 1. Cota
axes[0].plot(df['timestamp'], df['cota_cm'], marker='o', linestyle='-', color='#00d2ff', label='Cota (cm)')
axes[0].set_ylabel('Cota (cm)')
axes[0].set_title('Análise Hidrológica — Cota, Vz e Az (ERAB)')
axes[0].grid(True, alpha=0.3)
axes[0].legend()

# 2. Vz
axes[1].plot(df['timestamp'], df['vz_cm_h'], marker='o', linestyle='-', color='#ff6b6b', label='Vz (cm/h)')
axes[1].axhline(0, color='gray', linestyle='--', alpha=0.5)
axes[1].set_ylabel('Vz (cm/h)')
axes[1].grid(True, alpha=0.3)
axes[1].legend()

# 3. Az
axes[2].plot(df['timestamp'], df['az_cm_h2'], marker='o', linestyle='-', color='#ffd93d', label='Az (cm/h²)')
axes[2].axhline(0, color='gray', linestyle='--', alpha=0.5)
axes[2].set_ylabel('Az (cm/h²)')
axes[2].set_xlabel('Data / Hora')
axes[2].grid(True, alpha=0.3)
axes[2].legend()

plt.xticks(rotation=45)
plt.tight_layout()
plt.savefig(OUT_PNG, dpi=100)
print(f"✅ Gráfico salvo em: {OUT_PNG}")

# Histograma da cota
fig2, ax2 = plt.subplots(figsize=(8, 4))
ax2.hist(df['cota_cm'].dropna(), bins=10, color='#00d2ff', edgecolor='black')
ax2.set_title('Distribuição da Cota (36 leituras)')
ax2.set_xlabel('Cota (cm)')
ax2.set_ylabel('Frequência')
plt.tight_layout()
plt.savefig(BASE / "resultados" / "histograma_cota.png", dpi=100)
print(f"✅ Histograma salvo em: {BASE / 'resultados' / 'histograma_cota.png'}")
