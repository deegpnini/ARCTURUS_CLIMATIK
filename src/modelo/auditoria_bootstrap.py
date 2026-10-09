"""Porte mecanico da cel 56 do CLIMATIK5.ipynb. Corpo original preservado;
so os caminhos mudaram (data/ entradas, resultados/ saidas).
Rode da raiz: python -m src.modelo.auditoria_bootstrap"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
(ROOT / "resultados").mkdir(exist_ok=True)

# ============================================================
# AUDITORIA DO BOOTSTRAP — n_unicos baixo
# ============================================================
import numpy as np
import pandas as pd
import json
import lightgbm as lgb

with open("data/split_v3.json") as f:
    split = json.load(f)

treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']
eventos_teste = split['historico'][22:27]

# Carrega 1h
df = pd.read_csv("data/dataset_1h.csv")
target = 'target_1h'
feats = [c for c in df.columns if c not in ('timestamp', target)]
df['timestamp'] = pd.to_datetime(df['timestamp'])

m_tr = df['timestamp'] <= treino_fim
m_va = (df['timestamp'] >= val_ini) & (df['timestamp'] <= val_fim)

X = df[feats].values
y = df[target].values
X_tr, y_tr = X[m_tr], y[m_tr]
X_va, y_va = X[m_va], y[m_va]

params = {
    'objective': 'regression', 'metric': 'mae',
    'num_leaves': 31, 'max_depth': 5,
    'learning_rate': 0.05, 'verbose': -1,
    'min_data_in_leaf': 20,
    'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
}
train_data = lgb.Dataset(X_tr, label=y_tr)
val_data = lgb.Dataset(X_va, label=y_va, reference=train_data)
model = lgb.train(params, train_data, num_boost_round=1000,
                  valid_sets=[val_data],
                  callbacks=[lgb.early_stopping(50, verbose=False)])

idx_cota = feats.index('cota')

# ============================================================
# AUDITORIA 1: eventos tem tamanhos similares?
# ============================================================
print("="*80)
print("AUDITORIA 1 — TAMANHO DOS EVENTOS")
print("="*80)
eventos_dados = []
for i, ev in enumerate(eventos_teste, 1):
    ev_ini = pd.Timestamp(ev['inicio'])
    ev_fim = pd.Timestamp(ev['fim'])
    m_ev = (df['timestamp'] >= ev_ini) & (df['timestamp'] <= ev_fim)
    n = int(m_ev.sum())
    X_ev = X[m_ev]
    y_ev = y[m_ev]
    eventos_dados.append({
        'i': i, 'n': n, 'pico': ev['pico'],
        'y': y_ev,
        'persist': X_ev[:, idx_cota].astype(float),
        'lgb': model.predict(X_ev),
    })
    print(f"  evento {i}: n={n} | pico={ev['pico']:.0f}")

# ============================================================
# AUDITORIA 2: MAE por evento eh constante?
# ============================================================
print()
print("="*80)
print("AUDITORIA 2 — MAE POR EVENTO (estabilidade)")
print("="*80)

def mae(y, p):
    return float(np.mean(np.abs(y - p)))

for ed in eventos_dados:
    mp = mae(ed['y'], ed['persist'])
    ml = mae(ed['y'], ed['lgb'])
    print(f"  evento {ed['i']}: MAE_pers={mp:.4f} MAE_lgb={ml:.4f} delta={mp-ml:+.4f}")

# ============================================================
# AUDITORIA 3: distribuição dos deltas no bootstrap
# ============================================================
print()
print("="*80)
print("AUDITORIA 3 — DISTRIBUICAO DOS DELTAS (bootstrap)")
print("="*80)

N_BOOT = 1000
np.random.seed(42)
deltas = []
for b in range(N_BOOT):
    idxs = np.random.choice(len(eventos_dados), size=len(eventos_dados), replace=True)
    ys = np.concatenate([eventos_dados[i]['y'] for i in idxs])
    ps = np.concatenate([eventos_dados[i]['persist'] for i in idxs])
    ls = np.concatenate([eventos_dados[i]['lgb'] for i in idxs])
    deltas.append(mae(ys, ps) - mae(ys, ls))

deltas = np.array(deltas)
print(f"  Total bootstrap: {N_BOOT}")
print(f"  Valores unicos: {len(np.unique(deltas))}")
print(f"  Min: {deltas.min():.4f}")
print(f"  Max: {deltas.max():.4f}")
print(f"  Media: {deltas.mean():.4f}")
print(f"  Std: {deltas.std():.4f}")

# Top 10 valores mais comuns
from collections import Counter
c = Counter(np.round(deltas, 4))
print(f"\n  Top 10 valores mais frequentes:")
for val, freq in c.most_common(10):
    print(f"    {val}: {freq} vezes")

# ============================================================
# AUDITORIA 4: bootstrap POR LINHA (comparacao)
# ============================================================
print()
print("="*80)
print("AUDITORIA 4 — BOOTSTRAP POR LINHA (comparacao)")
print("="*80)
print("(nota: viola independencia, mas serve pra comparar)")

# Junta todas as linhas dos 5 eventos
ys_all = np.concatenate([ed['y'] for ed in eventos_dados])
ps_all = np.concatenate([ed['persist'] for ed in eventos_dados])
ls_all = np.concatenate([ed['lgb'] for ed in eventos_dados])
n_linhas = len(ys_all)

deltas_linha = []
for b in range(N_BOOT):
    idxs = np.random.choice(n_linhas, size=n_linhas, replace=True)
    deltas_linha.append(mae(ys_all[idxs], ps_all[idxs]) - mae(ys_all[idxs], ls_all[idxs]))

deltas_linha = np.array(deltas_linha)
print(f"  Valores unicos (linha): {len(np.unique(deltas_linha))}")
print(f"  Min: {deltas_linha.min():.4f}")
print(f"  Max: {deltas_linha.max():.4f}")
print(f"  Media: {deltas_linha.mean():.4f}")
print(f"  Std: {deltas_linha.std():.4f}")
print(f"  IC95%: [{np.percentile(deltas_linha, 2.5):.4f}, {np.percentile(deltas_linha, 97.5):.4f}]")

# ============================================================
# DIAGNOSTICO
# ============================================================
print()
print("="*80)
print("DIAGNOSTICO")
print("="*80)

n_unicos_evento = len(np.unique(np.round(deltas, 4)))
n_unicos_linha = len(np.unique(np.round(deltas_linha, 4)))

print(f"Bootstrap por evento: {n_unicos_evento} valores unicos de {N_BOOT}")
print(f"Bootstrap por linha:  {n_unicos_linha} valores unicos de {N_BOOT}")

if n_unicos_evento < 50:
    print()
    print("CAUSA RAIZ: com 5 eventos, cada reamostragem e' uma combinacao")
    print("de 5 escolhas entre 5. Total de combinacoes possiveis: ~126.")
    print("Por isso n_unicos ~= 190 (com repeticao).")
    print()
    print("IMPLICACAO: IC do bootstrap por evento tem resolucao limitada.")
    print("-> IC e' conservador (mais largo que o real), NAO invalido.")

print()
print("Diferenca evento vs linha:")
print(f"  std_evento: {deltas.std():.4f}")
print(f"  std_linha:  {deltas_linha.std():.4f}")
print(f"  ratio:      {deltas.std() / deltas_linha.std():.2f}x")
print()
print("Se ratio > 3: dependencia temporal alta (bootstrap por evento mais correto)")
print("Se ratio ~1:  sem dependencia, bootstrap por linha e' ok")