# ============================================================
# INVESTIGACAO — POR QUE DELTA SUBESTIMA MAGNITUDE?
# ============================================================
import pandas as pd
import numpy as np
import json

# Analisa o backtest: erro do delta vs magnitude real
res_df = pd.read_csv("/content/drive/MyDrive/ARCTURUS_ML/backtest_multi_evento.csv")

sub = res_df[res_df['h'] == '1h'].reset_index(drop=True)

# Carrega os dados do dataset para calcular magnitude real
# Simplificacao: usa pico do evento como proxy

print("="*80)
print("ANALISE: DELTA SUBESTIMA?")
print("="*80)

# Compara erro delta com pico do evento
print(f"\n{'Evento':12s} | {'Pico':5s} | {'MAE_delta':10s} | {'MAE_abs':10s} | {'Delta_vs_abs':12s}")
print("-"*80)
for _, r in sub.iterrows():
    delta = r['mae_abs'] - r['mae_delta']
    sinal = "+" if delta > 0 else ""
    print(f"{r['inicio'][:10]:12s} | {r['pico']:5.0f} | {r['mae_delta']:10.2f} | {r['mae_abs']:10.2f} | {sinal}{delta:+8.2f}")

# Correlacao
corr_pico_delta = sub['pico'].corr(sub['mae_delta'])
corr_pico_abs = sub['pico'].corr(sub['mae_abs'])
print(f"\nCorrelacao pico vs MAE_delta: {corr_pico_delta:+.3f}")
print(f"Correlacao pico vs MAE_abs:   {corr_pico_abs:+.3f}")

# Bin por tamanho
print(f"\nMAE medio por faixa de pico:")
faixas = [(0, 180), (180, 220), (220, 260), (260, 320)]
for low, high in faixas:
    s = sub[(sub['pico'] >= low) & (sub['pico'] < high)]
    if len(s) == 0: continue
    print(f"  pico {low}-{high}: N={len(s)} | MAE_pers={s['mae_pers'].mean():.2f} | MAE_abs={s['mae_abs'].mean():.2f} | MAE_delta={s['mae_delta'].mean():.2f}")