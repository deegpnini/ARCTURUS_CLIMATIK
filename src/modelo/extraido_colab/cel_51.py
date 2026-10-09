# ============================================================
# AUDITORIA CAUSALIDADE — TESTES 5, 7, 8 (corrigidos)
# ============================================================
import pandas as pd
import numpy as np

df = pd.read_csv("/content/dataset_1h.csv")
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp').reset_index(drop=True)

print("="*70)
print("TESTE 5 CORRIGIDO: cota(t) vs target_1h(t)")
print("="*70)

# Agora compara cota(t) com TARGET (cota em t+1h), nao com cota(t+15min)
mask = df['cota'].notna() & df['target_1h'].notna()
amostra = df[mask].head(1000)

if len(amostra) > 0:
    igual = (np.abs(amostra['cota'] - amostra['target_1h']) < 0.01).sum()
    total = len(amostra)
    print(f"  cota == target_1h em {igual}/{total} ({igual/total*100:.1f}%)")
    print(f"  -> esperado: < 30% (senao cota e' target)")
    if igual / total < 0.3:
        print(f"  ✅ OK: cota(t) NAO vaza target_1h")
    else:
        print(f"  ❌ ALERTA: suspeita de vazamento")
print()

print("="*70)
print("TESTE 7: correlacao cota vs target_6h (usando dataset_6h)")
print("="*70)

df6 = pd.read_csv("/content/dataset_6h.csv")
df6['timestamp'] = pd.to_datetime(df6['timestamp'])

mask = df6['cota'].notna() & df6['target_6h'].notna()
corr = df6[mask]['cota'].corr(df6[mask]['target_6h'])
print(f"  Correlacao cota vs target_6h: {corr:.4f}")
print(f"  -> esperado: menor que 1h (mais dificil)")
print()

print("="*70)
print("TESTE 8: features de lag usam apenas passado?")
print("="*70)

for col in ['cota_lag_15m', 'cota_lag_60m', 'cota_lag_360m']:
    if col not in df.columns:
        continue
    mask = df[col].notna() & df['cota'].notna()
    iguais = (df[mask][col] == df[mask]['cota']).sum()
    total = mask.sum()
    print(f"  {col}: {iguais}/{total} iguais a cota atual ({iguais/total*100:.2f}%)")
    print(f"    -> esperado: <5% (lag nao deve ser igual a cota atual)")
print()

print("="*70)
print("VEREDITO FINAL")
print("="*70)
print("Se TODOS os testes passaram: causalidade OK")