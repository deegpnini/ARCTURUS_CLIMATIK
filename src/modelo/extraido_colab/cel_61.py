# ============================================================
# A — VARIANTE DELTA
# target = cota_futura - cota_atual
# Roda teste C na variante DELTA vs ABSOLUTO
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb
from datetime import datetime, timedelta

# ============================================================
# 1. CARREGA DADOS
# ============================================================
with open("/content/split_v3.json") as f:
    split = json.load(f)

treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']

with open("/content/telemetria_84580000_2026.json") as f:
    tel = json.load(f)

leituras = {}
chuvas = {}
for it in tel['items']:
    ts = it.get('Data_Hora_Medicao', '')[:19]
    if not ts.startswith(('2026-09-21', '2026-09-22')):
        continue
    c = it.get('Cota_Adotada')
    v = None
    if c is not None and c != '':
        try: v = float(str(c).replace(',', '.'))
        except: pass
    leituras[ts] = v
    ch = it.get('Chuva_Adotada')
    cv = None
    if ch is not None and ch != '':
        try: cv = float(str(ch).replace(',', '.'))
        except: pass
    chuvas[ts] = cv

# ============================================================
# 2. TREINA MODELOS ABSOLUTO E DELTA
# ============================================================
modelos = {}

for h in ['1h', '3h', '6h']:
    print(f"\n=== HORIZONTE {h} ===")
    df = pd.read_csv(f"/content/dataset_{h}.csv")
    target_abs = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target_abs)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Cria target_delta = target_abs - cota_atual
    df['target_delta'] = df[target_abs] - df['cota']

    m_tr = df['timestamp'] <= treino_fim
    m_va = (df['timestamp'] >= val_ini) & (df['timestamp'] <= val_fim)

    X = df[feats].values
    y_abs = df[target_abs].values
    y_delta = df['target_delta'].values

    X_tr, X_va = X[m_tr], X[m_va]

    params = {
        'objective': 'regression', 'metric': 'mae',
        'num_leaves': 31, 'max_depth': 5,
        'learning_rate': 0.05, 'verbose': -1,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
    }

    # Modelo ABSOLUTO
    print(f"  Treinando ABSOLUTO...")
    y_tr_abs, y_va_abs = y_abs[m_tr], y_abs[m_va]
    train_abs = lgb.Dataset(X_tr, label=y_tr_abs)
    val_abs = lgb.Dataset(X_va, label=y_va_abs, reference=train_abs)
    model_abs = lgb.train(params, train_abs, num_boost_round=1000,
                          valid_sets=[val_abs],
                          callbacks=[lgb.early_stopping(50, verbose=False)])

    # Modelo DELTA
    print(f"  Treinando DELTA...")
    y_tr_delta, y_va_delta = y_delta[m_tr], y_delta[m_va]
    train_delta = lgb.Dataset(X_tr, label=y_tr_delta)
    val_delta = lgb.Dataset(X_va, label=y_va_delta, reference=train_delta)
    model_delta = lgb.train(params, train_delta, num_boost_round=1000,
                            valid_sets=[val_delta],
                            callbacks=[lgb.early_stopping(50, verbose=False)])

    modelos[h] = {
        'feats': feats,
        'model_abs': model_abs,
        'model_delta': model_delta,
        'best_iter_abs': model_abs.best_iteration,
        'best_iter_delta': model_delta.best_iteration,
    }
    print(f"  best_iter abs={model_abs.best_iteration} | delta={model_delta.best_iteration}")

# ============================================================
# 3. TESTE C — INPUT 446 (features iguais ao teste anterior)
# ============================================================
print("\n" + "="*80)
print("TESTE C — INPUT 446 cm (00:00 de 22/09)")
print("="*80)

T0 = "2026-09-22 00:00:00"
COTA_T0 = 446.0

# Features disponiveis em T0 (mesmas do teste C anterior)
def cota_lag(ts_ref, min):
    dt = datetime.strptime(ts_ref, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=min)
    return leituras.get(dt.strftime("%Y-%m-%d %H:%M:%S"))

feats_dict = {
    'cota': 446.0,
    'vazao': None,
    'cota_lag_15m': cota_lag(T0, 15),
    'cota_lag_30m': cota_lag(T0, 30),
    'cota_lag_60m': cota_lag(T0, 60),
    'cota_lag_180m': cota_lag(T0, 180),
    'cota_lag_360m': cota_lag(T0, 360),
    'cota_lag_720m': cota_lag(T0, 720),
    'cota_lag_1440m': cota_lag(T0, 1440),
    'delta_15m': None,
    'delta_60m': None,
    'delta_180m': None,
    'aceleracao_1h': None,
    'cota_std_12h': None,
    'cota_max_12h': None,
    'cota_min_12h': None,
    'chuva_15m': None,
    'chuva_60m': None,
    'chuva_180m': None,
    'chuva_360m': None,
    'chuva_720m': None,
    'chuva_1440m': None,
    'chuva_2880m': None,
    'sin_hora': np.sin(2*np.pi*0/24),  # 00:00
    'cos_hora': np.cos(2*np.pi*0/24),
    'sin_dia_ano': np.sin(2*np.pi*265/365),
    'cos_dia_ano': np.cos(2*np.pi*265/365),
}

ALVOS = {
    '1h': ('01:00', 424.0),
    '3h': ('03:00', 413.0),
    '6h': ('06:00', 375.0),
}

print(f"\n{'H':4s} | {'Alvo_ts':8s} | {'Alvo':6s} | {'Abs_pred':10s} | {'Delta_pred':10s} | {'Abs_real':10s} | {'Delta_real':10s}")
print("-"*80)

for h in ['1h', '3h', '6h']:
    m = modelos[h]
    feats = m['feats']

    X_pred = np.array([[feats_dict.get(f) for f in feats]], dtype=object)

    pred_abs = float(m['model_abs'].predict(X_pred)[0])
    pred_delta = float(m['model_delta'].predict(X_pred)[0])

    alvo_ts, alvo_obs = ALVOS[h]
    delta_real = alvo_obs - COTA_T0  # cota_futura - cota_atual

    # Reconstroi cota absoluta prevista a partir do delta
    pred_abs_from_delta = COTA_T0 + pred_delta

    err_abs = abs(pred_abs - alvo_obs)
    err_abs_from_delta = abs(pred_abs_from_delta - alvo_obs)
    err_delta = abs(pred_delta - delta_real)

    print(f"{h:4s} | {alvo_ts:8s} | {alvo_obs:6.0f} | {pred_abs:10.1f} | {pred_delta:+10.1f} | {alvo_obs:10.0f} | {delta_real:+10.1f}")
    print(f"     |          |        | err={err_abs:6.1f} | cota_abs={pred_abs_from_delta:6.1f} | err={err_abs_from_delta:6.1f} |")

# ============================================================
# 4. RESUMO
# ============================================================
print("\n" + "="*80)
print("COMPARACAO: ABSOLUTO vs DELTA no teste C")
print("="*80)
print(f"{'H':4s} | {'Obs':6s} | {'Abs_pred':10s} | {'Abs_err':8s} | {'Delta+Abs':10s} | {'Delta_err':10s}")
print("-"*80)

for h in ['1h', '3h', '6h']:
    m = modelos[h]
    feats = m['feats']
    X_pred = np.array([[feats_dict.get(f) for f in feats]], dtype=object)

    pred_abs = float(m['model_abs'].predict(X_pred)[0])
    pred_delta = float(m['model_delta'].predict(X_pred)[0])
    alvo_ts, alvo_obs = ALVOS[h]
    pred_delta_abs = COTA_T0 + pred_delta

    err_abs = abs(pred_abs - alvo_obs)
    err_delta_abs = abs(pred_delta_abs - alvo_obs)

    print(f"{h:4s} | {alvo_obs:6.0f} | {pred_abs:10.1f} | {err_abs:8.1f} | {pred_delta_abs:10.1f} | {err_delta_abs:10.1f}")

print()
print("INTERPRETACAO:")
print("  Se delta_err < abs_err: DELTA generaliza melhor")
print("  Se delta_err ~ abs_err: mesmo comportamento")
print("  Se delta_err > abs_err: ABSOLUTO e' melhor")

# Salva
resultado = {}
for h in ['1h', '3h', '6h']:
    m = modelos[h]
    feats = m['feats']
    X_pred = np.array([[feats_dict.get(f) for f in feats]], dtype=object)
    pred_abs = float(m['model_abs'].predict(X_pred)[0])
    pred_delta = float(m['model_delta'].predict(X_pred)[0])
    alvo_ts, alvo_obs = ALVOS[h]

    resultado[h] = {
        'alvo_obs': alvo_obs,
        'pred_abs': pred_abs,
        'pred_delta': pred_delta,
        'pred_delta_abs': COTA_T0 + pred_delta,
        'err_abs': abs(pred_abs - alvo_obs),
        'err_delta_abs': abs(COTA_T0 + pred_delta - alvo_obs),
    }

with open("/content/drive/MyDrive/ARCTURUS_ML/resultado_teste_c_delta.json", 'w') as f:
    json.dump(resultado, f, indent=2, default=str)
print(f"\n[OK] Salvo: resultado_teste_c_delta.json")