"""Porte mecanico da cel 62 do CLIMATIK5.ipynb. Corpo original preservado;
so os caminhos mudaram (data/ entradas, resultados/ saidas).
Rode da raiz: python -m src.modelo.backtest_estrutural"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
(ROOT / "resultados").mkdir(exist_ok=True)

# ============================================================
# ARCTURUS | BACKTEST ESTRUTURAL
# Protocolo PRE-REGISTRADO. Bootstrap por evento.
# 27 eventos | 3 horizontes | comparacao pareada
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb
from numpy.random import default_rng

# ============================================================
# 0. CONFIGURACAO
# ============================================================
N_BOOT = 10000
SEED = 42
rng = default_rng(SEED)

with open("data/split_v3.json") as f:
    split = json.load(f)

eventos = split['historico']  # 27 eventos

print("="*80)
print("ARCTURUS | BACKTEST ESTRUTURAL")
print(f"Eventos: {len(eventos)} | Bootstrap: {N_BOOT} | Unidade: evento")
print("="*80)

# Percentis de pico
picos = [ev['pico'] for ev in eventos]
P95 = float(np.percentile(picos, 95))
P99 = float(np.percentile(picos, 99))
print(f"P95 de pico: {P95:.0f} cm")
print(f"P99 de pico: {P99:.0f} cm")
print()

# ============================================================
# 1. FUNCOES DE METRICA E CLASSIFICACAO
# ============================================================
def mae(y, p):
    return float(np.mean(np.abs(y - p)))

def limite_empate(mae_concorrente):
    return max(0.10, 0.02 * mae_concorrente)

def classificar(mae_delta, mae_comp, diff_boot):
    """Classificacao pre-registrada."""
    n = len(diff_boot)
    diff_arr = np.array(diff_boot)
    mediana = float(np.median(diff_arr))
    ic_low = float(np.percentile(diff_arr, 2.5))
    ic_high = float(np.percentile(diff_arr, 97.5))

    wins = int(np.sum(diff_arr > limite_empate(mae_comp)))
    losses = int(np.sum(diff_arr < -limite_empate(mae_comp)))
    ties = n - wins - losses

    lim = limite_empate(mae_comp)

    if mae_delta < mae_comp and mediana > 0 and ic_low > 0 and wins >= 17:
        return "DELTA_SUPERIOR", mediana, ic_low, ic_high, wins, ties, losses
    elif mae_delta < mae_comp and wins >= 17:
        return "DELTA_PROMISSOR", mediana, ic_low, ic_high, wins, ties, losses
    elif abs(mae_delta - mae_comp) <= lim:
        return "EQUIVALENTE", mediana, ic_low, ic_high, wins, ties, losses
    elif ic_high < 0 and losses >= 17:
        return "DELTA_INFERIOR", mediana, ic_low, ic_high, wins, ties, losses
    else:
        return "INCONCLUSIVO", mediana, ic_low, ic_high, wins, ties, losses

# ============================================================
# 2. BACKTEST POR HORIZONTE
# ============================================================
resultados_por_evento = []  # lista de dicts com evento, h, modelo, mae

for h in ['1h', '3h', '6h']:
    print(f"\n{'='*80}")
    print(f"HORIZONTE {h}")
    print(f"{'='*80}")

    df = pd.read_csv(f"data/dataset_{h}.csv")
    target_abs = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target_abs)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['target_delta'] = df[target_abs] - df['cota']

    X_all = df[feats].values
    y_abs_all = df[target_abs].values
    y_delta_all = df['target_delta'].values

    idx_cota = feats.index('cota')

    params = {
        'objective': 'regression', 'metric': 'mae',
        'num_leaves': 31, 'max_depth': 5,
        'learning_rate': 0.05, 'verbose': -1,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
    }

    print(f"\n{'Evento':14s} | {'N':5s} | {'Pico':5s} | {'MAE_pers':9s} | {'MAE_abs':9s} | {'MAE_delta':9s}")
    print("-"*80)

    for i, ev in enumerate(eventos):
        ev_ini = pd.Timestamp(ev['inicio'])
        ev_fim = pd.Timestamp(ev['fim'])
        m_test = (df['timestamp'] >= ev_ini) & (df['timestamp'] <= ev_fim)
        m_train = ~m_test

        if m_test.sum() == 0:
            continue

        X_tr = X_all[m_train]
        X_te = X_all[m_test]
        y_abs_tr = y_abs_all[m_train]
        y_abs_te = y_abs_all[m_test]
        y_delta_tr = y_delta_all[m_train]

        persist_te = X_te[:, idx_cota].astype(float)
        mae_pers = mae(y_abs_te, persist_te)

        train_abs = lgb.Dataset(X_tr, label=y_abs_tr)
        model_abs = lgb.train(params, train_abs, num_boost_round=200)
        pred_abs = model_abs.predict(X_te)
        mae_abs = mae(y_abs_te, pred_abs)

        train_delta = lgb.Dataset(X_tr, label=y_delta_tr)
        model_delta = lgb.train(params, train_delta, num_boost_round=200)
        pred_delta = model_delta.predict(X_te)
        pred_delta_abs = persist_te + pred_delta
        mae_delta = mae(y_abs_te, pred_delta_abs)

        label = f"{ev['inicio'][:10]} ({i+1})"
        print(f"{label:14s} | {int(m_test.sum()):5d} | {ev['pico']:5.0f} | {mae_pers:9.2f} | {mae_abs:9.2f} | {mae_delta:9.2f}")

        resultados_por_evento.append({
            'h': h, 'i': i+1, 'inicio': ev['inicio'],
            'pico': ev['pico'], 'n': int(m_test.sum()),
            'mae_pers': mae_pers, 'mae_abs': mae_abs, 'mae_delta': mae_delta,
        })

res_df = pd.DataFrame(resultados_por_evento)

# ============================================================
# 3. BOOTSTRAP POR EVENTO
# ============================================================
print("\n" + "="*80)
print("BOOTSTRAP POR EVENTO (N=10000)")
print("="*80)

def bootstrap_diff(maes_delta, maes_comp):
    """Bootstrap por evento: reamostra eventos, recalcula MAE medio."""
    n = len(maes_delta)
    diffs = []
    for b in range(N_BOOT):
        idx = rng.integers(0, n, size=n)
        md = np.mean([maes_delta[j] for j in idx])
        mc = np.mean([maes_comp[j] for j in idx])
        diffs.append(mc - md)
    return np.array(diffs)

def analisar_horizonte(sub, h):
    print(f"\n{'='*80}")
    print(f"ANALISE {h}")
    print(f"{'='*80}")

    md = sub['mae_delta'].values
    ma = sub['mae_abs'].values
    mp = sub['mae_pers'].values

    print(f"MAE medio delta: {md.mean():.3f}")
    print(f"MAE medio abs:   {ma.mean():.3f}")
    print(f"MAE medio pers:  {mp.mean():.3f}")
    print(f"MAE mediano delta: {np.median(md):.3f}")

    # DELTA vs ABS
    print(f"\n--- DELTA vs ABS ---")
    diff_boot = bootstrap_diff(md, ma)
    r = classificar(md.mean(), ma.mean(), diff_boot)
    print(f"  Diferenca mediana: {r[1]:+.3f} cm")
    print(f"  IC95%: [{r[2]:+.3f}, {r[3]:+.3f}]")
    print(f"  V/T/D: {r[4]}/{r[5]}/{r[6]}")
    print(f"  Classificacao: {r[0]}")

    # DELTA vs PERSIST
    print(f"\n--- DELTA vs PERSIST ---")
    diff_boot = bootstrap_diff(md, mp)
    r = classificar(md.mean(), mp.mean(), diff_boot)
    print(f"  Diferenca mediana: {r[1]:+.3f} cm")
    print(f"  IC95%: [{r[2]:+.3f}, {r[3]:+.3f}]")
    print(f"  V/T/D: {r[4]}/{r[5]}/{r[6]}")
    print(f"  Classificacao: {r[0]}")

# Analise por horizonte
for h in ['1h', '3h', '6h']:
    sub = res_df[res_df['h'] == h].reset_index(drop=True)
    if len(sub) > 0:
        analisar_horizonte(sub, h)

# ============================================================
# 4. ANALISE DE SEVERIDADE (1h como principal)
# ============================================================
print("\n" + "="*80)
print("ANALISE DE SEVERIDADE (1h)")
print("="*80)

sub_1h = res_df[res_df['h'] == '1h'].reset_index(drop=True)

for nome, cond in [
    ('GLOBAL', lambda s: s),
    ('SEVERO (>P95)', lambda s: s[s['pico'] > P95]),
    ('EXTREMO (>P99)', lambda s: s[s['pico'] > P99]),
]:
    s = cond(sub_1h)
    print(f"\n--- {nome} ---")
    print(f"  N eventos: {len(s)}")
    if len(s) == 0:
        print("  Sem eventos")
        continue

    md = s['mae_delta'].values
    ma = s['mae_abs'].values
    mp = s['mae_pers'].values

    print(f"  MAE medio delta: {md.mean():.3f}")
    print(f"  MAE medio abs:   {ma.mean():.3f}")
    print(f"  MAE medio pers:  {mp.mean():.3f}")

    if len(s) >= 5:
        # Bootstrap
        for comp_name, mc in [('ABS', ma), ('PERS', mp)]:
            diff_boot = bootstrap_diff(md, mc)
            ic_low = np.percentile(diff_boot, 2.5)
            ic_high = np.percentile(diff_boot, 97.5)
            wins = int(np.sum(diff_boot > limite_empate(mc.mean())))
            print(f"  vs {comp_name}: mediana_diff={np.median(diff_boot):+.3f} IC=[{ic_low:+.3f}, {ic_high:+.3f}] wins={wins}/{len(s)}")
    else:
        print(f"  INCONCLUSIVO (n={len(s)} < 5)")

# ============================================================
# 5. TESTE LEAVE-EXTREMES-OUT (dependencia de extremos)
# ============================================================
print("\n" + "="*80)
print("TESTE LEAVE-EXTREMES-OUT (1h)")
print("="*80)

s_sem_ext = sub_1h[sub_1h['pico'] <= P99]
print(f"Eventos sem extremos (pico <= P99): {len(s_sem_ext)}")

if len(s_sem_ext) > 0:
    md = s_sem_ext['mae_delta'].values
    ma = s_sem_ext['mae_abs'].values
    diff_boot = bootstrap_diff(md, ma)
    ic_low = np.percentile(diff_boot, 2.5)
    wins = int(np.sum(diff_boot > limite_empate(ma.mean())))
    mediana = np.median(diff_boot)

    print(f"Sem extremos: mediana_diff={mediana:+.3f} IC=[{ic_low:+.3f}, {np.percentile(diff_boot, 97.5):+.3f}] wins={wins}/{len(s_sem_ext)}")

    if mediana > 0 and ic_low > 0 and wins >= int(0.6 * len(s_sem_ext)):
        print("-> Nao ha dependencia exclusiva de extremos")
    else:
        print("-> ATENCAO: vantagem depende de extremos")

# ============================================================
# 6. DECISAO FINAL
# ============================================================
print("\n" + "="*80)
print("DECISAO POR HORIZONTE")
print("="*80)

for h in ['1h', '3h', '6h']:
    sub = res_df[res_df['h'] == h].reset_index(drop=True)
    if len(sub) == 0: continue
    md = sub['mae_delta'].values
    ma = sub['mae_abs'].values
    mp = sub['mae_pers'].values

    diff_abs = bootstrap_diff(md, ma)
    r_abs = classificar(md.mean(), ma.mean(), diff_abs)
    diff_pers = bootstrap_diff(md, mp)
    r_pers = classificar(md.mean(), mp.mean(), diff_pers)

    print(f"\n{h}:")
    print(f"  DELTA vs ABS:    {r_abs[0]}")
    print(f"  DELTA vs PERS:   {r_pers[0]}")

# Salva
res_df.to_csv("resultados/backtest_multi_evento.csv", index=False)
print(f"\n[OK] Salvo: backtest_multi_evento.csv")