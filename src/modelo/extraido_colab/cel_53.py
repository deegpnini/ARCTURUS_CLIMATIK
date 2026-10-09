# ============================================================
# C — BOOTSTRAP POR EVENTO (incerteza)
# Reamostra EVENTOS, nao linhas.
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb

# Carrega split
with open("/content/split_v3.json") as f:
    split = json.load(f)

treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']
teste_ini = split['historico'][22]['inicio']
teste_fim = split['historico'][26]['fim']

eventos_teste = split['historico'][22:27]

# ============================================================
# Bootstrap config
# ============================================================
N_BOOT = 1000
np.random.seed(42)

print("="*80)
print("BOOTSTRAP POR EVENTO — 1000 reamostragens")
print("="*80)
print()

def mae(y, p):
    return float(np.mean(np.abs(y - p)))

def mae_extremos(y, p, limiar):
    mask = y > limiar
    if mask.sum() == 0: return None
    return float(np.mean(np.abs(y[mask] - p[mask])))

# ============================================================
# Loop horizontes
# ============================================================
for h in ['1h', '3h', '6h']:
    print(f"\n{'='*80}")
    print(f"HORIZONTE {h}")
    print(f"{'='*80}")

    # Carrega dataset
    df = pd.read_csv(f"/content/dataset_{h}.csv")
    target = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Split
    m_tr = df['timestamp'] <= treino_fim
    m_va = (df['timestamp'] >= val_ini) & (df['timestamp'] <= val_fim)

    X = df[feats].values
    y = df[target].values

    X_tr, y_tr = X[m_tr], y[m_tr]
    X_va, y_va = X[m_va], y[m_va]

    # Treina modelo
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
    # Separa dados por evento
    # ============================================================
    eventos_dados = []
    for i, ev in enumerate(eventos_teste, 1):
        ev_ini = pd.Timestamp(ev['inicio'])
        ev_fim = pd.Timestamp(ev['fim'])
        m_ev = (df['timestamp'] >= ev_ini) & (df['timestamp'] <= ev_fim)
        if m_ev.sum() == 0: continue

        X_ev = X[m_ev]
        y_ev = y[m_ev]
        persist_ev = X_ev[:, idx_cota].astype(float)
        pred_ev = model.predict(X_ev)

        eventos_dados.append({
            'evento': i,
            'y': y_ev,
            'persist': persist_ev,
            'lgb': pred_ev,
            'n': int(m_ev.sum()),
            'pico': ev['pico'],
        })

    # ============================================================
    # MAE por evento (original)
    # ============================================================
    print(f"\nMAE por evento (original):")
    print(f"  {'Evento':10s} | {'N':5s} | {'Pico':6s} | {'MAE_pers':10s} | {'MAE_lgb':10s} | {'Delta':8s}")
    for ed in eventos_dados:
        mp = mae(ed['y'], ed['persist'])
        ml = mae(ed['y'], ed['lgb'])
        print(f"  {'evento '+str(ed['evento']):10s} | {ed['n']:5d} | {ed['pico']:6.0f} | {mp:10.2f} | {ml:10.2f} | {mp-ml:+8.2f}")

    # ============================================================
    # Bootstrap: reamostra EVENTOS
    # ============================================================
    n_eventos = len(eventos_dados)
    maes_pers_boot = []
    maes_lgb_boot = []
    deltas_boot = []

    for b in range(N_BOOT):
        # Escolhe eventos com reposicao
        idx_escolhidos = np.random.choice(n_eventos, size=n_eventos, replace=True)

        # Junta dados dos eventos reamostrados
        ys = []
        ps = []
        ls = []
        for idx in idx_escolhidos:
            ys.append(eventos_dados[idx]['y'])
            ps.append(eventos_dados[idx]['persist'])
            ls.append(eventos_dados[idx]['lgb'])

        y_boot = np.concatenate(ys)
        p_boot = np.concatenate(ps)
        l_boot = np.concatenate(ls)

        mp = mae(y_boot, p_boot)
        ml = mae(y_boot, l_boot)

        maes_pers_boot.append(mp)
        maes_lgb_boot.append(ml)
        deltas_boot.append(mp - ml)

    maes_pers_boot = np.array(maes_pers_boot)
    maes_lgb_boot = np.array(maes_lgb_boot)
    deltas_boot = np.array(deltas_boot)

    # ============================================================
    # Intervalos de confiança 95%
    # ============================================================
    def ic95(arr):
        lo = np.percentile(arr, 2.5)
        hi = np.percentile(arr, 97.5)
        return lo, hi

    print(f"\nBootstrap ({N_BOOT} amostras):")
    print(f"  MAE persist:  media={np.mean(maes_pers_boot):.2f}  IC95%=[{ic95(maes_pers_boot)[0]:.2f}, {ic95(maes_pers_boot)[1]:.2f}]")
    print(f"  MAE LightGBM: media={np.mean(maes_lgb_boot):.2f}  IC95%=[{ic95(maes_lgb_boot)[0]:.2f}, {ic95(maes_lgb_boot)[1]:.2f}]")
    print(f"  Delta (pers - lgb):")
    print(f"    media={np.mean(deltas_boot):+.2f}")
    print(f"    IC95%=[{ic95(deltas_boot)[0]:+.2f}, {ic95(deltas_boot)[1]:+.2f}]")

    # Delta positivo em quantos bootstrap?
    pct_positivo = (deltas_boot > 0).mean() * 100
    print(f"    % bootstrap com delta > 0: {pct_positivo:.1f}%")

    # ============================================================
    # Avaliar P95 e P99 (sub-bootstrap)
    # ============================================================
    print(f"\nBootstrap em EXTREMOS:")
    y_all = np.concatenate([ed['y'] for ed in eventos_dados])
    p95 = np.percentile(y_all, 95)
    p99 = np.percentile(y_all, 99)
    print(f"  P95={p95:.1f} | P99={p99:.1f}")

    deltas_p95_boot = []
    deltas_p99_boot = []
    for b in range(N_BOOT):
        idx_escolhidos = np.random.choice(n_eventos, size=n_eventos, replace=True)
        ys = np.concatenate([eventos_dados[idx]['y'] for idx in idx_escolhidos])
        ps = np.concatenate([eventos_dados[idx]['persist'] for idx in idx_escolhidos])
        ls = np.concatenate([eventos_dados[idx]['lgb'] for idx in idx_escolhidos])

        # P95
        m95p = mae_extremos(ys, ps, p95)
        m95l = mae_extremos(ys, ls, p95)
        if m95p is not None and m95l is not None:
            deltas_p95_boot.append(m95p - m95l)

        # P99
        m99p = mae_extremos(ys, ps, p99)
        m99l = mae_extremos(ys, ls, p99)
        if m99p is not None and m99l is not None:
            deltas_p99_boot.append(m99p - m99l)

    if deltas_p95_boot:
        d95 = np.array(deltas_p95_boot)
        print(f"  Delta P95: media={np.mean(d95):+.2f}  IC95%=[{ic95(d95)[0]:+.2f}, {ic95(d95)[1]:+.2f}]")
        print(f"  % >0: {(d95 > 0).mean()*100:.1f}%")

    if deltas_p99_boot:
        d99 = np.array(deltas_p99_boot)
        print(f"  Delta P99: media={np.mean(d99):+.2f}  IC95%=[{ic95(d99)[0]:+.2f}, {ic95(d99)[1]:+.2f}]")
        print(f"  % >0: {(d99 > 0).mean()*100:.1f}%")

print(f"\n{'='*80}")
print("FIM DO BOOTSTRAP")
print(f"{'='*80}")