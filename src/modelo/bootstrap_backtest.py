"""Porte mecanico da cel 66 do CLIMATIK5.ipynb. Corpo original preservado;
so os caminhos mudaram (data/ entradas, resultados/ saidas).
Rode da raiz: python -m src.modelo.bootstrap_backtest"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.chdir(ROOT)
(ROOT / "resultados").mkdir(exist_ok=True)

# ============================================================
# BACKTEST ESTRUTURAL — BOOTSTRAP POR EVENTO
# Protocolo pre-registrado. Sem escolher regra depois.
# ============================================================
import pandas as pd
import numpy as np
import json
from numpy.random import default_rng

# Carrega o CSV ja produzido
res_df = pd.read_csv("resultados/backtest_multi_evento.csv")

N_BOOT = 10000
SEED = 42
rng = default_rng(SEED)

picos = res_df[res_df['h'] == '1h']['pico'].values
P95 = float(np.percentile(picos, 95))
P99 = float(np.percentile(picos, 99))

print("="*80)
print("BOOTSTRAP POR EVENTO — 10.000 reamostragens")
print(f"P95 pico: {P95:.0f} | P99 pico: {P99:.0f}")
print("="*80)

def limite_empate(mae_comp):
    return max(0.10, 0.02 * mae_comp)

def bootstrap_diff(maes_delta, maes_comp, n_boot=N_BOOT):
    """Reamostra EVENTOS. Retorna array de (MAE_comp - MAE_delta)."""
    n = len(maes_delta)
    diffs = np.empty(n_boot)
    for b in range(n_boot):
        idx = rng.integers(0, n, size=n)
        md = maes_delta[idx].mean()
        mc = maes_comp[idx].mean()
        diffs[b] = mc - md
    return diffs

def classificar(mae_delta, mae_comp, diff_boot):
    lim = limite_empate(mae_comp)
    mediana = float(np.median(diff_boot))
    ic_low = float(np.percentile(diff_boot, 2.5))
    ic_high = float(np.percentile(diff_boot, 97.5))
    wins = int((diff_boot > lim).sum() / N_BOOT * len(diff_boot))
    # Melhor: contar eventos individuais com tolerancia
    return mediana, ic_low, ic_high

def classificar_v2(maes_delta, maes_comp):
    """
    Classificacao por EVENTO (nao por bootstrap).
    Usa tolerancia max(0.10, 2%).
    """
    n = len(maes_delta)
    lim = max(0.10, 0.02 * np.mean(maes_comp))
    wins = int(np.sum((maes_comp - maes_delta) > lim))
    losses = int(np.sum((maes_comp - maes_delta) < -lim))
    ties = n - wins - losses
    return wins, ties, losses, lim

# ============================================================
# ANALISE POR HORIZONTE
# ============================================================
for h in ['1h', '3h', '6h']:
    print(f"\n{'='*80}")
    print(f"HORIZONTE {h}")
    print(f"{'='*80}")

    sub = res_df[res_df['h'] == h].reset_index(drop=True)
    md = sub['mae_delta'].values
    ma = sub['mae_abs'].values
    mp = sub['mae_pers'].values

    print(f"\nMAE medio: persist={mp.mean():.3f} | abs={ma.mean():.3f} | delta={md.mean():.3f}")
    print(f"MAE mediano: persist={np.median(mp):.3f} | abs={np.median(ma):.3f} | delta={np.median(md):.3f}")

    # DELTA vs PERSIST
    print(f"\n--- DELTA vs PERSIST ---")
    wins, ties, losses, lim = classificar_v2(md, mp)
    print(f"  Vitorias/Empates/Derrotas: {wins}/{ties}/{losses} (limite={lim:.2f})")
    diff_boot = bootstrap_diff(md, mp)
    med = float(np.median(diff_boot))
    ic_low = float(np.percentile(diff_boot, 2.5))
    ic_high = float(np.percentile(diff_boot, 97.5))
    print(f"  Diferenca mediana: {med:+.3f}")
    print(f"  IC95%: [{ic_low:+.3f}, {ic_high:+.3f}]")
    if ic_low > 0 and wins >= 17 and md.mean() < mp.mean():
        print(f"  -> DELTA_SUPERIOR")
    elif ic_low > 0:
        print(f"  -> DELTA_PROMISSOR")
    elif ic_high < 0:
        print(f"  -> DELTA_INFERIOR")
    else:
        print(f"  -> INCONCLUSIVO")

    # DELTA vs ABS
    print(f"\n--- DELTA vs ABS ---")
    wins, ties, losses, lim = classificar_v2(md, ma)
    print(f"  Vitorias/Empates/Derrotas: {wins}/{ties}/{losses} (limite={lim:.2f})")
    diff_boot = bootstrap_diff(md, ma)
    med = float(np.median(diff_boot))
    ic_low = float(np.percentile(diff_boot, 2.5))
    ic_high = float(np.percentile(diff_boot, 97.5))
    print(f"  Diferenca mediana: {med:+.3f}")
    print(f"  IC95%: [{ic_low:+.3f}, {ic_high:+.3f}]")
    if ic_low > 0 and wins >= 17 and md.mean() < ma.mean():
        print(f"  -> DELTA_SUPERIOR")
    elif ic_low > 0:
        print(f"  -> DELTA_PROMISSOR")
    elif ic_high < 0:
        print(f"  -> DELTA_INFERIOR")
    else:
        print(f"  -> INCONCLUSIVO")

# ============================================================
# ANALISE DE SEVERIDADE (1h)
# ============================================================
print("\n" + "="*80)
print("ANALISE DE SEVERIDADE (1h)")
print("="*80)

sub_1h = res_df[res_df['h'] == '1h'].reset_index(drop=True)

for nome, cond in [
    ('GLOBAL', lambda s: s),
    ('SEVERO (>P95)', lambda s: s[s['pico'] > P95]),
    ('EXTREMO (>P99)', lambda s: s[s['pico'] > P99]),
    ('SEM EXTREMOS (<=P99)', lambda s: s[s['pico'] <= P99]),
]:
    s = cond(sub_1h)
    print(f"\n--- {nome} (N={len(s)}) ---")
    if len(s) < 5:
        print("  INCONCLUSIVO (n < 5)")
        continue

    md = s['mae_delta'].values
    ma = s['mae_abs'].values
    mp = s['mae_pers'].values
    print(f"  MAE medio: persist={mp.mean():.3f} | abs={ma.mean():.3f} | delta={md.mean():.3f}")

    for comp_nome, mc in [('PERSIST', mp), ('ABS', ma)]:
        wins, ties, losses, lim = classificar_v2(md, mc)
        diff_boot = bootstrap_diff(md, mc)
        med = float(np.median(diff_boot))
        ic_low = float(np.percentile(diff_boot, 2.5))
        ic_high = float(np.percentile(diff_boot, 97.5))
        print(f"  DELTA vs {comp_nome}: V/E/D={wins}/{ties}/{losses} | med={med:+.3f} | IC95=[{ic_low:+.3f}, {ic_high:+.3f}]")

# ============================================================
# LEAVE-EXTREMES-OUT
# ============================================================
print("\n" + "="*80)
print("LEAVE-EXTREMES-OUT (remove eventos > P99)")
print("="*80)

for h in ['1h', '3h', '6h']:
    sub = res_df[res_df['h'] == h]
    sub_sem = sub[sub['pico'] <= P99]

    print(f"\n{h}: {len(sub_sem)}/{len(sub)} eventos sem extremos")
    if len(sub_sem) < 5:
        print("  INCONCLUSIVO")
        continue

    md = sub_sem['mae_delta'].values
    ma = sub_sem['mae_abs'].values
    mp = sub_sem['mae_pers'].values

    print(f"  MAE medio delta: {md.mean():.3f}")
    print(f"  MAE medio abs:   {ma.mean():.3f}")

    diff_boot = bootstrap_diff(md, ma)
    ic_low = float(np.percentile(diff_boot, 2.5))
    med = float(np.median(diff_boot))
    print(f"  Delta vs abs: med={med:+.3f} IC95 low={ic_low:+.3f}")

    if med > 0 and ic_low > 0:
        print("  -> Vantagem NAO depende de extremos")
    else:
        print("  -> ATENCAO: vantagem pode depender de extremos")