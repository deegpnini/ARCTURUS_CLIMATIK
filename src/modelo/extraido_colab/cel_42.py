import pandas as pd, os

candidatos = [
    '/content/drive/MyDrive/ARCTURUS_CLIMATIK/climatik_completo.csv',
    '/content/drive/MyDrive/CLIMATIK/epagri_MASTER.csv',
    '/content/drive/MyDrive/ARCTURUS_CLIMATIK/inmet_sc_completo_2024_2026.csv',
]

for c in candidatos:
    if os.path.exists(c):
        print(f"\n=== {os.path.basename(c)} ===")
        df = pd.read_csv(c, nrows=5)
        print("Colunas:", list(df.columns))
        print("Shape (parcial):", df.shape)
        print(df.head(3))