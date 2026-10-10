import json
import pandas as pd
from datetime import datetime

print("=" * 70)
print("  1. Leituras do cache em 21/09 19h-21h")
print("=" * 70)
with open("data/telemetria_84580000_2026.json", encoding="utf-8") as f:
    items = json.load(f).get("items") or []

for it in items:
    ts = it.get("Data_Hora_Medicao", "")
    if ts.startswith(("2026-09-21 19:", "2026-09-21 20:", "2026-09-21 21:")):
        print(f"  {ts} | cota={it.get('Cota_Adotada')} | chuva={it.get('Chuva_Adotada')}")

print()
print("=" * 70)
print("  2. Features do dataset_1h.csv em 22/09 00:00")
print("=" * 70)
df = pd.read_csv("data/dataset_1h.csv")
df["timestamp"] = pd.to_datetime(df["timestamp"])

t = pd.Timestamp("2026-09-22 00:00:00")
row = df[df["timestamp"] == t]

if row.empty:
    print(f"  Timestamp {t} NAO esta no dataset_1h.csv")
    # Ver o mais proximo
    df_ord = df.sort_values("timestamp")
    pos = df_ord["timestamp"].searchsorted(t)
    print(f"  Mais proximo ANTES: {df_ord.iloc[max(0,pos-1)]['timestamp']}")
    print(f"  Mais proximo DEPOIS: {df_ord.iloc[min(len(df_ord)-1,pos)]['timestamp']}")
else:
    r = row.iloc[0]
    print(f"  Timestamp {t} ESTA no dataset_1h.csv")
    print()
    for col in df.columns:
        print(f"  {col}: {r[col]}")
