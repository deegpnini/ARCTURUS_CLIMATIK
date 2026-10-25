import json
import sqlite3
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
DB_PATH = BASE / "data" / "arcturus.db"
REGIME_FILE = BASE / "data" / "regime_atual.json"

if not REGIME_FILE.exists():
    print("⚠️ regime_atual.json não encontrado. Nada a gravar.")
    exit(0)

with open(REGIME_FILE, "r") as f:
    reg = json.load(f)

# --- LEITURA DA COTA REAL ---
COTA_FILE = BASE / "tubarao_saneamento_dados.json"
cota_cm = None
if COTA_FILE.exists():
    with open(COTA_FILE, "r") as f:
        cota_cm = json.load(f).get("cota_cm")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

cursor.execute("""
    INSERT INTO leituras (timestamp, cota_cm, vz_cm_h, az_cm_h2, regime)
    VALUES (?, ?, ?, ?, ?)
""", (
    datetime.now().isoformat(),
    cota_cm,  # Lida do tubarao_saneamento_dados.json
    reg.get("delta_60m", 0.0),
    reg.get("aceleracao_az", 0.0),
    reg.get("regime", "NORMAL")
))

conn.commit()
conn.close()
print(f"✅ Leitura gravada no SQLite: vz={reg.get('delta_60m', 0.0):.1f}, az={reg.get('aceleracao_az', 0.0):.1f}, regime={reg.get('regime', 'NORMAL')}")
