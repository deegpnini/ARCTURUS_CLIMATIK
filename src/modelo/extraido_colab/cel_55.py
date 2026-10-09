# ============================================================
# C — BOOTSTRAP POR EVENTO (v2 com correção de IC)
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb

with open("/content/split_v3.json") as f:
    split = json.load(f)

treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']

eventos_teste = split['historico'][22:27]
N_BOOT = 1000
np.random.seed(42)

def mae(y, p):
    return float(np.mean(np.abs(y - p)))

def mae_extremos(y, p, limiar):
    mask = y > limiar
    if mask.sum() == 0: return None
    return float(np.mean(np.abs(y[mask] - p[mask])))

def ic95_valido(arr):
    arr = np.array(arr)
    n_unicos = len(np.unique(arr))
    if n_unicos < 5:
        return None, None, n_unicos
    lo = float(np.percentile(arr, 2.5))
    hi = float(np.percentile(arr, 97.5))
    return lo, hi, n_unicos

def interpretar_ic(arr, nome):
    lo, hi, n_unicos = ic95_valido(arr)
    if lo is None:
        print(f"  {nome}: IC INVALIDO ({n_unicos} valores unicos) - inconclusivo")
        return None
    media = float(np.mean(arr))
    pct_pos = float((np.array(arr) > 0).mean() * 100)
    cruza_zero = lo <= 0 <= hi
    status = "INCONCLUSIVO" if cruza_zero else ("GANHO ROBUSTO" if media > 0 else "PERDA ROBUSTA")
    print(f"  {nome}: media={media:+.2f}  IC95%=[{lo:+.2f}, {hi:+.2f}]  "
          f"n_unicos={n_unicos}  %pos={pct_pos:.1f}%  -> {status}")
    return (media, lo, hi, n_unicos)

# ============================================================
# LOOP HORIZONTES
# ============================================================
for h in ['1h', '3h', '6h']:
    print(f"\n{'='*80}")
    print(f"HORIZONTE {h}")
    print(f"{'='*80}")

    df = pd.read_csv(f"/content/dataset_{h}.csv")
    target = f'target_{h}'
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

    # Separa por evento
    eventos_dados = []
    for i, ev in enumerate(eventos_teste, 1):
        ev_ini = pd.Timestamp(ev['inicio'])
        ev_fim = pd.Timestamp(ev['fim'])
        m_ev = (df['timestamp'] >= ev_ini) & (df['timestamp'] <= ev_fim)
        if m_ev.sum() == 0: continue
        X_ev = X[m_ev]
        y_ev = y[m_ev]
        eventos_dados.append({
            'evento': i,
            'y': y_ev,
            'persist': X_ev[:, idx_cota].astype(float),
            'lgb': model.predict(X_ev),
            'n': int(m_ev.sum()),
            'pico': ev['pico'],
        })

    n_eventos = len(eventos_dados)

    # Bootstrap global
    deltas_boot = []
    for b in range(N_BOOT):
        idxs = np.random.choice(n_eventos, size=n_eventos, replace=True)
        ys = np.concatenate([eventos_dados[i]['y'] for i in idxs])
        ps = np.concatenate([eventos_dados[i]['persist'] for i in idxs])
        ls = np.concatenate([eventos_dados[i]['lgb'] for i in idxs])
        deltas_boot.append(mae(ys, ps) - mae(ys, ls))

    # Bootstrap P95 e P99 — só eventos que tem amostras no limiar
    y_all = np.concatenate([ed['y'] for ed in eventos_dados])
    p95 = np.percentile(y_all, 95)
    p99 = np.percentile(y_all, 99)
    print(f"  P95={p95:.1f} | P99={p99:.1f}")

    deltas_p95_boot = []
    deltas_p99_boot = []
    for b in range(N_BOOT):
        idxs = np.random.choice(n_eventos, size=n_eventos, replace=True)
        ys = np.concatenate([eventos_dados[i]['y'] for i in idxs])
        ps = np.concatenate([eventos_dados[i]['persist'] for i in idxs])
        ls = np.concatenate([eventos_dados[i]['lgb'] for i in idxs])

        m95p = mae_extremos(ys, ps, p95)
        m95l = mae_extremos(ys, ls, p95)
        if m95p is not None and m95l is not None:
            deltas_p95_boot.append(m95p - m95l)

        m99p = mae_extremos(ys, ps, p99)
        m99l = mae_extremos(ys, ls, p99)
        if m99p is not None and m99l is not None:
            deltas_p99_boot.append(m99p - m99l)

    print(f"\n  Bootstrap GLOBAL:")
    interpretar_ic(deltas_boot, "Delta global (pers - lgb)")
    print(f"\n  Bootstrap P95:")
    interpretar_ic(deltas_p95_boot, "Delta P95")
    print(f"\n  Bootstrap P99:")
    interpretar_ic(deltas_p99_boot, "Delta P99")

print(f"\n{'='*80}")
print("FIM")
print(f"{'='*80}")