
# ============================================================
# BACKTEST MULTI-EVENTO — Absoluto vs Delta vs Persistencia
# Leave-one-event-out: para cada evento, treina com os outros
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb

with open("/content/split_v3.json") as f:
    split = json.load(f)

# Eventos historicos
eventos_hist = split['historico']  # 27 eventos
eventos_op = split['operacional']  # 1 evento (446)

# Para multi-evento, usar so os 27 historicos
# (o 446 fica como caso operacional separado)
eventos = eventos_hist

print(f"Total de eventos para backtest: {len(eventos)}")
print(f"Eventos:")
for i, ev in enumerate(eventos, 1):
    print(f"  [{i:2d}] {ev['inicio'][:10]} | pico {ev['pico']:.0f} | dur {ev['duracao_h']:.0f}h")

# ============================================================
# PARA CADA HORIZONTE, RODA LEAVE-ONE-EVENT-OUT
# ============================================================
def mae(y, p):
    return float(np.mean(np.abs(y - p)))

resultados = []

for h in ['1h', '3h', '6h']:
    print(f"\n{'='*80}")
    print(f"HORIZONTE {h}")
    print(f"{'='*80}")

    df = pd.read_csv(f"/content/dataset_{h}.csv")
    target_abs = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target_abs)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['target_delta'] = df[target_abs] - df['cota']

    X_all = df[feats].values
    y_abs_all = df[target_abs].values
    y_delta_all = df['target_delta'].values
    ts_all = df['timestamp'].values

    idx_cota = feats.index('cota')

    params = {
        'objective': 'regression', 'metric': 'mae',
        'num_leaves': 31, 'max_depth': 5,
        'learning_rate': 0.05, 'verbose': -1,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
    }

    # Cabecalho
    print(f"\n{'Evento':12s} | {'N':5s} | {'Pico':5s} | {'MAE_pers':9s} | {'MAE_abs':9s} | {'MAE_delta':10s}")
    print("-"*80)

    for i, ev in enumerate(eventos):
        ev_ini = pd.Timestamp(ev['inicio'])
        ev_fim = pd.Timestamp(ev['fim'])

        # Mascara do evento (teste)
        m_test = (df['timestamp'] >= ev_ini) & (df['timestamp'] <= ev_fim)

        # Treino: tudo que NAO e' desse evento
        # mas respeitar o split: so usa treino que nao contem o evento
        # Simplificacao: usa todos os outros eventos (leave-one-out)
        m_train = ~m_test

        if m_test.sum() == 0:
            continue

        X_tr = X_all[m_train]
        X_te = X_all[m_test]
        y_abs_tr = y_abs_all[m_train]
        y_abs_te = y_abs_all[m_test]
        y_delta_tr = y_delta_all[m_train]
        y_delta_te = y_delta_all[m_test]

        # Persistencia
        persist_te = X_te[:, idx_cota].astype(float)
        mae_pers = mae(y_abs_te, persist_te)

        # Modelo absoluto
        train_abs = lgb.Dataset(X_tr, label=y_abs_tr)
        model_abs = lgb.train(params, train_abs, num_boost_round=200)
        pred_abs = model_abs.predict(X_te)
        mae_abs = mae(y_abs_te, pred_abs)

        # Modelo delta
        train_delta = lgb.Dataset(X_tr, label=y_delta_tr)
        model_delta = lgb.train(params, train_delta, num_boost_round=200)
        pred_delta = model_delta.predict(X_te)
        pred_delta_abs = X_te[:, idx_cota].astype(float) + pred_delta
        mae_delta = mae(y_abs_te, pred_delta_abs)

        # Marca quem ganha
        ganhador = "delta" if mae_delta < mae_abs else ("abs" if mae_abs < mae_delta else "empate")
        if mae_pers < min(mae_abs, mae_delta):
            ganhador = "persist"

        label = f"{ev['inicio'][:10]} ({i+1})"
        print(f"{label:12s} | {int(m_test.sum()):5d} | {ev['pico']:5.0f} | {mae_pers:9.2f} | {mae_abs:9.2f} | {mae_delta:10.2f} | {ganhador}")

        resultados.append({
            'h': h,
            'evento': i+1,
            'inicio': ev['inicio'],
            'pico': ev['pico'],
            'n': int(m_test.sum()),
            'mae_pers': mae_pers,
            'mae_abs': mae_abs,
            'mae_delta': mae_delta,
            'ganhador': ganhador,
        })

# ============================================================
# RESUMO AGREGADO
# ============================================================
print("\n" + "="*80)
print("RESUMO MULTI-EVENTO")
print("="*80)

res_df = pd.DataFrame(resultados)

for h in ['1h', '3h', '6h']:
    sub = res_df[res_df['h'] == h]
    print(f"\n{h}:")
    print(f"  Eventos testados: {len(sub)}")
    print(f"  Delta ganhou: {sum(sub['ganhador'] == 'delta')}")
    print(f"  Absoluto ganhou: {sum(sub['ganhador'] == 'abs')}")
    print(f"  Persist ganhou: {sum(sub['ganhador'] == 'persist')}")
    print(f"  MAE medio persist: {sub['mae_pers'].mean():.2f}")
    print(f"  MAE medio absoluto: {sub['mae_abs'].mean():.2f}")
    print(f"  MAE medio delta: {sub['mae_delta'].mean():.2f}")

# Salva
res_df.to_csv("/content/drive/MyDrive/ARCTURUS_ML/backtest_multi_evento.csv", index=False)
print(f"\n[OK] Salvo: backtest_multi_evento.csv")