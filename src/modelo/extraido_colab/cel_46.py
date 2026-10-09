# ============================================================
# ARCTURUS — AUTO-LOCALIZADOR + BENCHMARK LightGBM
# ============================================================
# Este script:
# 1. Monta o Google Drive
# 2. Procura os 4 arquivos em qualquer pasta
# 3. Copia para /content/
# 4. Instala LightGBM
# 5. Roda o benchmark completo

!pip install -q lightgbm

from google.colab import drive
import os
import shutil
import json
import numpy as np
import pandas as pd
import lightgbm as lgb

# ============================================================
# 1. MONTAR DRIVE
# ============================================================
drive.mount('/content/drive')
DRIVE = '/content/drive/MyDrive'

# ============================================================
# 2. PROCURAR OS ARQUIVOS
# ============================================================
ARQUIVOS_ALVO = [
    "dataset_1h.csv",
    "dataset_3h.csv",
    "dataset_6h.csv",
    "split_v3.json",
]

print("="*70)
print("PROCURANDO ARQUIVOS NO DRIVE...")
print("="*70)

encontrados = {}

for root, dirs, files in os.walk(DRIVE):
    for f in files:
        if f in ARQUIVOS_ALVO and f not in encontrados:
            path = os.path.join(root, f)
            encontrados[f] = path
            print(f"  [OK] {f}")
            print(f"       {path}")

# Verifica se achou todos
faltando = [a for a in ARQUIVOS_ALVO if a not in encontrados]
if faltando:
    print(f"\n[!] FALTAM: {faltando}")
    print("\nColoque esses arquivos no Drive em alguma pasta e re-execute.")
else:
    print(f"\n[OK] Todos os 4 arquivos encontrados!")

    # Copia para /content/
    for nome, path in encontrados.items():
        shutil.copy2(path, f"/content/{nome}")
    print("[OK] Copiados para /content/")