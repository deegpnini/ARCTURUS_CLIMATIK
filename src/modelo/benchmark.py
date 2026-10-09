"""Porte mecanico da cel 50 do CLIMATIK5.ipynb (persistencia vs LightGBM absoluto).
Corpo original preservado; so imports, caminhos e encoding foram alterados."""
import json
from pathlib import Path

import numpy as np
import pandas as pd
import lightgbm as lgb

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
PASTA = ROOT / "resultados"
PASTA.mkdir(exist_ok=True)

# ============================================================
# ARCTURUS ML — CÉLULA 2
# Benchmark: persistencia + GBM caseiro + LightGBM
# Split congelado V3. Sem expectativa de resultado.
# ============================================================

with open(DATA / "split_v3.json", encoding="utf-8") as f:
    split = json.load(f)

# Limites do split congelado
treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']
teste_ini = split['historico'][22]['inicio']
teste_fim = split['historico'][26]['fim']

print("Split congelado V3:")
print(f"  Treino: <= {treino_fim}")
print(f"  Val:    {val_ini} a {val_fim}")
print(f"  Teste:  {teste_ini} a {teste_fim}")
print()

# ============================================================
# Métricas
# ============================================================
def mae(y_true, y_pred):
    return float(np.mean(np.abs(y_true - y_pred)))

def mae_extremos(y_true, y_pred, limiar):
    mask = y_true > limiar
    if mask.sum() == 0:
        return None, 0
    return float(np.mean(np.abs(y_true[mask] - y_pred[mask]))), int(mask.sum())

def mae_subida(y_true, y_pred, X, idx_delta, limiar=5.0):
    """MAE só nos exemplos onde delta_60m > limiar"""
    mask = np.array([x[idx_delta] is not None and x[idx_delta] > limiar for x in X])
    if mask.sum() == 0:
        return None, 0
    return float(np.mean(np.abs(y_true[mask] - y_pred[mask]))), int(mask.sum())

# ============================================================
# Loop nos 3 horizontes
# ============================================================
resultados = {}

for h in ['1h', '3h', '6h']:
    print(f"\n{'='*70}")
    print(f"HORIZONTE {h}")
    print(f"{'='*70}")

    df = pd.read_csv(DATA / f"dataset_{h}.csv")
    target = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target)]

    df['timestamp'] = pd.to_datetime(df['timestamp'])
    m_tr = df['timestamp'] <= treino_fim
    m_va = (df['timestamp'] >= val_ini) & (df['timestamp'] <= val_fim)
    m_te = (df['timestamp'] >= teste_ini) & (df['timestamp'] <= teste_fim)

    X = df[feats].values
    y = df[target].values

    X_tr, y_tr = X[m_tr], y[m_tr]
    X_va, y_va = X[m_va], y[m_va]
    X_te, y_te = X[m_te], y[m_te]

    print(f"  Treino: {len(X_tr)} | Val: {len(X_va)} | Teste: {len(X_te)}")

    # Percentis do target (calculados sobre o dataset inteiro)
    p95 = np.percentile(y, 95)
    p99 = np.percentile(y, 99)
    print(f"  P95: {p95:.1f} | P99: {p99:.1f}")

    # ----------------------------
    # Baseline 1: persistencia
    # ----------------------------
    idx_cota = feats.index('cota')
    persist_te = X_te[:, idx_cota].astype(float)

    mae_pers_global = mae(y_te, persist_te)
    mae_pers_p95, n95 = mae_extremos(y_te, persist_te, p95)
    mae_pers_p99, n99 = mae_extremos(y_te, persist_te, p99)

    idx_delta = feats.index('delta_60m') if 'delta_60m' in feats else None
    if idx_delta is not None:
        mae_pers_sub, n_sub = mae_subida(y_te, persist_te, X_te, idx_delta)
    else:
        mae_pers_sub, n_sub = None, 0

    # ----------------------------
    # LightGBM
    # ----------------------------
    params = {
        'objective': 'regression',
        'metric': 'mae',
        'num_leaves': 31,
        'max_depth': 5,
        'learning_rate': 0.05,
        'verbose': -1,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8,
        'bagging_fraction': 0.8,
        'bagging_freq': 5,
    }

    train_data = lgb.Dataset(X_tr, label=y_tr)
    val_data = lgb.Dataset(X_va, label=y_va, reference=train_data)

    model = lgb.train(
        params, train_data,
        num_boost_round=1000,
        valid_sets=[val_data],
        callbacks=[lgb.early_stopping(50, verbose=False)]
    )

    pred_te = model.predict(X_te)

    mae_lgb_global = mae(y_te, pred_te)
    mae_lgb_p95, _ = mae_extremos(y_te, pred_te, p95)
    mae_lgb_p99, _ = mae_extremos(y_te, pred_te, p99)
    if idx_delta is not None:
        mae_lgb_sub, _ = mae_subida(y_te, pred_te, X_te, idx_delta)
    else:
        mae_lgb_sub = None

    # ----------------------------
    # Impressão
    # ----------------------------
    print(f"\n  {'Métrica':30s} | {'Persist':10s} | {'LightGBM':10s}")
    print(f"  {'-'*30} | {'-'*10} | {'-'*10}")
    print(f"  {'MAE global':30s} | {mae_pers_global:10.2f} | {mae_lgb_global:10.2f}")

    if mae_pers_p95 is not None:
        print(f"  {f'MAE > P95 (n={n95})':30s} | {mae_pers_p95:10.2f} | {mae_lgb_p95:10.2f}")

    if mae_pers_p99 is not None:
        print(f"  {f'MAE > P99 (n={n99})':30s} | {mae_pers_p99:10.2f} | {mae_lgb_p99:10.2f}")

    if mae_pers_sub is not None:
        print(f"  {f'MAE na subida (n={n_sub})':30s} | {mae_pers_sub:10.2f} | {mae_lgb_sub:10.2f}")

    resultados[h] = {
        'persist_global': mae_pers_global,
        'lgb_global': mae_lgb_global,
        'persist_p95': mae_pers_p95,
        'lgb_p95': mae_lgb_p95,
        'persist_p99': mae_pers_p99,
        'lgb_p99': mae_lgb_p99,
        'persist_sub': mae_pers_sub,
        'lgb_sub': mae_lgb_sub,
        'n95': n95,
        'n99': n99,
        'n_sub': n_sub,
        'best_iter': model.best_iteration,
        'feature_cols': feats,
        'model': model,
    }

# ============================================================
# RESUMO FINAL
# ============================================================
print(f"\n{'='*70}")
print("RESUMO — Persist | GBM caseiro | LightGBM")
print(f"{'='*70}")
print(f"{'H':4s} | {'Persist':12s} | {'GBM caseiro':12s} | {'LightGBM':12s} | {'Ganho':10s}")
print(f"{'-'*70}")

gbm_caseiro = {'1h': 6.93, '3h': 8.73, '6h': 10.21}
for h in ['1h', '3h', '6h']:
    r = resultados[h]
    ganho = (1 - r['lgb_global'] / r['persist_global']) * 100
    print(f"{h:4s} | {r['persist_global']:10.2f} cm | {gbm_caseiro[h]:10.2f} cm | {r['lgb_global']:10.2f} cm | {ganho:+7.1f}%")

# ============================================================
# EXTREMOS — comparação detalhada
# ============================================================
print(f"\n{'='*70}")
print("EXTREMOS — Persist vs LightGBM")
print(f"{'='*70}")
print(f"{'H':4s} | {'P95 persist':12s} | {'P95 lgb':12s} | {'P99 persist':12s} | {'P99 lgb':12s}")
print(f"{'-'*70}")
for h in ['1h', '3h', '6h']:
    r = resultados[h]
    p95_p = f"{r['persist_p95']:.2f}" if r['persist_p95'] else "-"
    p95_l = f"{r['lgb_p95']:.2f}" if r['lgb_p95'] else "-"
    p99_p = f"{r['persist_p99']:.2f}" if r['persist_p99'] else "-"
    p99_l = f"{r['lgb_p99']:.2f}" if r['lgb_p99'] else "-"
    print(f"{h:4s} | {p95_p:>12s} | {p95_l:>12s} | {p99_p:>12s} | {p99_l:>12s}")

# ============================================================
# FEATURE IMPORTANCE — 1h (top 15)
# ============================================================
print(f"\n{'='*70}")
print("TOP 15 FEATURES (LightGBM 1h)")
print(f"{'='*70}")
r = resultados['1h']
imp = pd.DataFrame({
    'feature': r['feature_cols'],
    'gain': r['model'].feature_importance(importance_type='gain'),
    'split': r['model'].feature_importance(importance_type='split'),
}).sort_values('gain', ascending=False)

print(imp.head(15).to_string(index=False))

# ============================================================
# SALVA NO DRIVE
# ============================================================
saida = {
    h: {k: v for k, v in resultados[h].items() if k not in ('model', 'feature_cols')}
    for h in resultados
}
with open(f"{PASTA}/resultado_lightgbm.json", 'w') as f:
    json.dump(saida, f, indent=2, default=str)

print(f"\n[OK] Resultado salvo: {PASTA}/resultado_lightgbm.json")