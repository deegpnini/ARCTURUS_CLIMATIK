# ============================================================
# CONTAGEM FORMAL: DELTA ACERTA DIRECAO?
# ============================================================
import pandas as pd
import numpy as np
import json

res_df = pd.read_csv("/content/drive/MyDrive/ARCTURUS_ML/backtest_multi_evento.csv")

print("="*80)
print("CONTAGEM DE SINAIS — DELTA ACERTA DIRECAO?")
print("="*80)

for h in ['1h', '3h', '6h']:
    sub = res_df[res_df['h'] == h]
    # Nao temos delta previsto vs delta real no CSV
    # Precisamos adicionar isso ao backtest
    print(f"\n{h}: analise precisa de retreino (nao esta no CSV)")
    print(f"  (o CSV so tem MAE, nao direcao prevista)")

# Para fazer de verdade, precisamos do backtest com:
# - delta_previsto por evento
# - delta_real por evento
# - contagem de acertos de direcao
print("\n-> precisa rodar backtest v2 com logging de direcao")