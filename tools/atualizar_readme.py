import os
import json
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

print("=" * 70)
print("  ARCTURUS - Atualizar README e docs")
print("=" * 70)
print()

# Verificar estado
readme_path = ROOT / "README.md"
req_path = ROOT / "requirements.txt"
license_path = ROOT / "LICENSE"

print("[1] Estado atual:")
print(f"  README.md existe: {readme_path.exists()}")
print(f"  requirements.txt existe: {req_path.exists()}")
print(f"  LICENSE existe: {license_path.exists()}")
print()

# Manifesto
manifesto_path = ROOT / "modelos" / "manifesto_producao.json"
if manifesto_path.exists():
    manifest = json.load(open(manifesto_path, encoding="utf-8"))
    print("[2] Manifesto de producao:")
    for h, info in manifest["horizontes"].items():
        print(f"  {h}: {info['n_features']} features, {info['num_boost_round']} rounds")
else:
    print("[2] Manifesto NAO encontrado")
print()
