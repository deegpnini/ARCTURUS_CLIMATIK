# ============================================================
# AVALIACAO POR EVENTO — LightGBM vs Persistencia
# Para cada um dos 5 eventos do teste
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb

# Carrega split
with open("/content/split_v3.json") as f:
    split = json.load(f)

# Limites
treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']
teste_ini = split['historico'][22]['inicio']
teste_fim = split['historico'][26]['fim']

# Eventos do teste
eventos_teste = split['historico'][22:27]
print(f"Eventos no teste: {len(eventos_teste)}")
for i, ev in enumerate(eventos_teste, 1):
    print(f"  [{i}] {ev['inicio'][:16]} a {ev['fim'][:16]} (pico {ev['pico']:.0f} cm)")
print()

# ============================================================
# FUNCAO DE METRICAS
# ============================================================
def mae(y, p):
    return float(np.mean(np.abs(y - p)))

def rmse(y, p):
    return float(np.sqrt(np.mean((y - p) ** 2)))

# ============================================================
# AVALIACAO POR HORIZONTE
# ============================================================
for h in ['1h', '3h', '6h']:
    print(f"\n{'='*80}")
    print(f"HORIZONTE {h} — AVALIACAO POR EVENTO")
    print(f"{'='*80}")

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

    print(f"\n{'Evento':30s} | {'N':6s} | {'Pico':6s} | {'MAE_pers':10s} | {'MAE_lgb':10s} | {'Delta':8s}")
    print(f"{'-'*30} | {'-'*6} | {'-'*6} | {'-'*10} | {'-'*10} | {'-'*8}")

    resultados_eventos = []
    for i, ev in enumerate(eventos_teste, 1):
        ev_ini = pd.Timestamp(ev['inicio'])
        ev_fim = pd.Timestamp(ev['fim'])

        m_ev = (df['timestamp'] >= ev_ini) & (df['timestamp'] <= ev_fim)
        if m_ev.sum() == 0:
            continue

        X_ev = X[m_ev]
        y_ev = y[m_ev]

        persist_ev = X_ev[:, idx_cota].astype(float)
        pred_ev = model.predict(X_ev)

        mae_pers = mae(y_ev, persist_ev)
        mae_lgb = mae(y_ev, pred_ev)
        delta = mae_pers - mae_lgb
        sinal = "+" if delta > 0 else ""

        # Label curto do evento
        label = f"{ev['inicio'][:10]} ({i})"
        print(f"{label:30s} | {m_ev.sum():6d} | {ev['pico']:6.0f} | {mae_pers:10.2f} | {mae_lgb:10.2f} | {sinal}{delta:+6.2f}")

        resultados_eventos.append({
            'evento': i,
            'inicio': ev['inicio'],
            'fim': ev['fim'],
            'pico': ev['pico'],
            'n': int(m_ev.sum()),
            'mae_persist': mae_pers,
            'mae_lgb': mae_lgb,
            'delta': delta,
        })

    # Resumo do horizonte
    if resultados_eventos:
        deltas = [r['delta'] for r in resultados_eventos]
        n_ganhos = sum(1 for d in deltas if d > 0)
        n_perdas = sum(1 for d in deltas if d < 0)
        print()
        print(f"  Resumo {h}:")
        print(f"    LightGBM ganhou em {n_ganhos}/{len(resultados_eventos)} eventos")
        print(f"    LightGBM perdeu em {n_perdas}/{len(resultados_eventos)} eventos")
        print(f"    Delta medio: {np.mean(deltas):+.2f} cm")
        print(f"    Pior caso (LGB perdeu): {min(deltas):+.2f} cm")
        print(f"    Melhor caso (LGB ganhou): {max(deltas):+.2f} cm")