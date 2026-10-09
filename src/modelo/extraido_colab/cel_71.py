# ============================================================
# BACKTEST v2 — CONTAGEM DE DIRECAO
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb

with open("/content/split_v3.json") as f:
    split = json.load(f)

eventos = split['historico']
print(f"Eventos: {len(eventos)}\n")

params = {
    'objective': 'regression', 'metric': 'mae',
    'num_leaves': 31, 'max_depth': 5,
    'learning_rate': 0.05, 'verbose': -1,
    'min_data_in_leaf': 20,
    'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
}

for h in ['1h', '3h', '6h']:
    df = pd.read_csv(f"/content/dataset_{h}.csv")
    target_abs = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target_abs)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['target_delta'] = df[target_abs] - df['cota']

    X_all = df[feats].values
    y_abs_all = df[target_abs].values
    y_delta_all = df['target_delta'].values
    idx_cota = feats.index('cota')

    acertos_delta = 0
    acertos_abs = 0
    total = 0

    for i, ev in enumerate(eventos):
        ev_ini = pd.Timestamp(ev['inicio'])
        ev_fim = pd.Timestamp(ev['fim'])
        m_test = (df['timestamp'] >= ev_ini) & (df['timestamp'] <= ev_fim)
        m_train = ~m_test

        if m_test.sum() == 0:
            continue

        X_tr = X_all[m_train]
        X_te = X_all[m_test]
        y_abs_te = y_abs_all[m_test]
        y_abs_tr = y_abs_all[m_train]
        y_delta_tr = y_delta_all[m_train]

        persist_te = X_te[:, idx_cota].astype(float)
        delta_real = y_abs_te - persist_te

        train_abs = lgb.Dataset(X_tr, label=y_abs_tr)
        m_abs = lgb.train(params, train_abs, num_boost_round=200)
        pred_abs = m_abs.predict(X_te)

        train_delta = lgb.Dataset(X_tr, label=y_delta_tr)
        m_delta = lgb.train(params, train_delta, num_boost_round=200)
        pred_delta = m_delta.predict(X_te)

        for j in range(len(y_abs_te)):
            real_delta = delta_real[j]
            if real_delta == 0:
                continue
            abs_delta = pred_abs[j] - persist_te[j]
            delta_pred = pred_delta[j]

            if np.sign(abs_delta) == np.sign(real_delta): acertos_abs += 1
            if np.sign(delta_pred) == np.sign(real_delta): acertos_delta += 1
            total += 1

    print(f"=== {h} ===")
    print(f"  Total: {total}")
    print(f"  Delta acertou direcao: {acertos_delta}/{total} ({acertos_delta/total*100:.1f}%)")
    print(f"  ABS acertou direcao:   {acertos_abs}/{total} ({acertos_abs/total*100:.1f}%)")
    print()