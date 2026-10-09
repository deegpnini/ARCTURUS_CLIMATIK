from google.colab import files
import os
import shutil

DRIVE = '/content/drive/MyDrive'

print("Faça upload dos 4 arquivos:")
print("  - dataset_1h.csv")
print("  - dataset_3h.csv")
print("  - dataset_6h.csv")
print("  - split_v3.json")
uploaded = files.upload()

# Salva no Drive
os.makedirs(f"{DRIVE}/ARCTURUS_ML", exist_ok=True)
for nome in uploaded:
    shutil.copy2(f"/content/{nome}", f"{DRIVE}/ARCTURUS_ML/{nome}")
    print(f"  [OK] {nome} -> {DRIVE}/ARCTURUS_ML/")

print("\nArquivos salvos no Drive. Da proxima vez, so rodar a Celula 1.")