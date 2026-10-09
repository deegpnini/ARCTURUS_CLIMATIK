
# ============================================================
# ARCTURUS ML — CÉLULA 1
# Monta Drive, copia os 4 arquivos, instala LightGBM
# ============================================================
!pip install -q lightgbm

from google.colab import drive
import os, shutil, json
import numpy as np
import pandas as pd
import lightgbm as lgb

drive.mount('/content/drive')
DRIVE = '/content/drive/MyDrive'
PASTA = f"{DRIVE}/ARCTURUS_ML"

ARQUIVOS = ["dataset_1h.csv", "dataset_3h.csv", "dataset_6h.csv", "split_v3.json"]

print(f"Procurando em: {PASTA}")
if not os.path.exists(PASTA):
    print(f"[!] Pasta NAO existe")
else:
    print(f"[OK] Pasta existe")
    for f in os.listdir(PASTA):
        print(f"  - {f}")
    print()
    for nome in ARQUIVOS:
        origem = f"{PASTA}/{nome}"
        if os.path.exists(origem):
            shutil.copy2(origem, f"/content/{nome}")
            print(f"[OK] {nome} copiado")
        else:
            print(f"[!] {nome} NAO encontrado")