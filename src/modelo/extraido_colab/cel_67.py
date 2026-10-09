# ============================================================
# A — TESTE DELTA NO EVENTO 446
# Modelo congelado. Gap respeitado. Features ausentes = NaN.
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb
from datetime import datetime, timedelta

# ============================================================
# 1. CARREGA SPLIT E TELEMETRIA
# ============================================================
with open("/content/split_v3.json") as f:
    split = json.load(f)

treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']

with open("/content/telemetria_84580000_2026.json") as f:
    tel = json.load(f)

# Mapa de leituras
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
# 2. TREINA MODELOS (ABSOLUTO + DELTA) COM SPLIT CONGELADO
# ============================================================
modelos = {}

for h in ['1h', '3h', '6h']:
    print(f"Treinando modelo {h}...")

    df = pd.read_csv(f"/content/dataset_{h}.csv")
    target_abs = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target_abs)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
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

    train_abs = lgb.Dataset(X_tr, label=y_abs[m_tr])
    val_abs = lgb.Dataset(X_va, label=y_abs[m_va], reference=train_abs)
    model_abs = lgb.train(params, train_abs, num_boost_round=1000,
                          valid_sets=[val_abs],
                          callbacks=[lgb.early_stopping(50, verbose=False)])

    train_delta = lgb.Dataset(X_tr, label=y_delta[m_tr])
    val_delta = lgb.Dataset(X_va, label=y_delta[m_va], reference=train_delta)
    model_delta = lgb.train(params, train_delta, num_boost_round=1000,
                            valid_sets=[val_delta],
                            callbacks=[lgb.early_stopping(50, verbose=False)])

    modelos[h] = {
        'feats': feats,
        'model_abs': model_abs,
        'model_delta': model_delta,
    }
    print(f"  abs iter={model_abs.best_iteration} | delta iter={model_delta.best_iteration}")

# ============================================================
# 3. CONSTROI FEATURES EM T0 = 22/09 00:00
# ============================================================
T0 = "2026-09-22 00:00:00"
COTA_T0 = 446.0

def cota_lag(ts_ref, min):
    dt = datetime.strptime(ts_ref, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=min)
    return leituras.get(dt.strftime("%Y-%m-%d %H:%M:%S"))

def chuva_janela(ts_ref, minutos):
    dt_ref = datetime.strptime(ts_ref, "%Y-%m-%d %H:%M:%S")
    total = 0
    validos = 0
    n_esperado = minutos // 15 + 1
    for i in range(n_esperado):
        dt = dt_ref - timedelta(minutes=15*i)
        ts = dt.strftime("%Y-%m-%d %H:%M:%S")
        ch = chuvas.get(ts)
        if ch is not None:
            total += ch
            validos += 1
    if validos / n_esperado < 0.9:
        return None
    return total

feats_dict = {
    'cota': COTA_T0,
    'vazao': None,
    'cota_lag_15m': cota_lag(T0, 15),
    'cota_lag_30m': cota_lag(T0, 30),
    'cota_lag_60m': cota_lag(T0, 60),
    'cota_lag_180m': cota_lag(T0, 180),
    'cota_lag_360m': cota_lag(T0, 360),
    'cota_lag_720m': cota_lag(T0, 720),
    'cota_lag_1440m': cota_lag(T0, 1440),
    'delta_15m': None, 'delta_60m': None, 'delta_180m': None,
    'aceleracao_1h': None,
    'cota_std_12h': None, 'cota_max_12h': None, 'cota_min_12h': None,
    'chuva_15m': None, 'chuva_60m': None, 'chuva_180m': None,
    'chuva_360m': chuva_janela(T0, 360),
    'chuva_720m': chuva_janela(T0, 720),
    'chuva_1440m': chuva_janela(T0, 1440),
    'chuva_2880m': chuva_janela(T0, 2880),
    'sin_hora': np.sin(2*np.pi*0/24),
    'cos_hora': np.cos(2*np.pi*0/24),
    'sin_dia_ano': np.sin(2*np.pi*265/365),
    'cos_dia_ano': np.cos(2*np.pi*265/365),
}

# ============================================================
# 4. PREDIZ E COMPARA
# ============================================================
ALVOS = {
    '1h': ('2026-09-22 01:00:00', 424.0),
    '3h': ('2026-09-22 03:00:00', 413.0),
    '6h': ('2026-09-22 06:00:00', 375.0),
}

print("\n" + "="*90)
print(f"TESTE NO EVENTO 446 — T0 = {T0}")
print("="*90)
print(f"\n{'H':4s} | {'Alvo':6s} | {'Persist':9s} | {'Abs':9s} | {'Delta':9s} | {'Delta+Cota':11s} | {'err_pers':9s} | {'err_abs':8s} | {'err_delta':9s}")
print("-"*100)

resultados = {}
for h in ['1h', '3h', '6h']:
    m = modelos[h]
    X_pred = np.array([[feats_dict.get(f) for f in m['feats']]], dtype=object)

    pred_abs = float(m['model_abs'].predict(X_pred)[0])
    pred_delta = float(m['model_delta'].predict(X_pred)[0])
    pred_delta_abs = COTA_T0 + pred_delta

    alvo_ts, alvo_obs = ALVOS[h]
    persist = COTA_T0

    err_p = abs(persist - alvo_obs)
    err_a = abs(pred_abs - alvo_obs)
    err_d = abs(pred_delta_abs - alvo_obs)

    print(f"{h:4s} | {alvo_obs:6.0f} | {persist:9.0f} | {pred_abs:9.1f} | {pred_delta:+9.1f} | {pred_delta_abs:11.1f} | {err_p:9.2f} | {err_a:8.2f} | {err_d:9.2f}")

    resultados[h] = {
        'alvo_obs': alvo_obs,
        'persist': persist,
        'pred_abs': pred_abs,
        'pred_delta': pred_delta,
        'pred_delta_abs': pred_delta_abs,
        'err_persist': err_p,
        'err_abs': err_a,
        'err_delta': err_d,
    }

# ============================================================
# 5. RESUMO
# ============================================================
print("\n" + "="*90)
print("RESUMO — ERRO NO EVENTO 446 (extrapolacao)")
print("="*90)
print(f"{'H':4s} | {'Obs':6s} | {'Err_persist':11s} | {'Err_abs':9s} | {'Err_delta':10s} | {'Vencedor':12s}")
print("-"*90)
for h in ['1h', '3h', '6h']:
    r = resultados[h]
    erros = {'persist': r['err_persist'], 'abs': r['err_abs'], 'delta': r['err_delta']}
    venc = min(erros, key=erros.get)
    print(f"{h:4s} | {r['alvo_obs']:6.0f} | {r['err_persist']:11.2f} | {r['err_abs']:9.2f} | {r['err_delta']:10.2f} | {venc:12s}")

print()
print("NOTA: gap 195 min. 20 de 24 features indisponiveis em T0.")
print("O modelo esta cego para a trajetoria durante o gap.")

# Salva
with open("/content/drive/MyDrive/ARCTURUS_ML/teste_446_delta.json", 'w') as f:
    json.dump(resultados, f, indent=2, default=str)
print(f"\n[OK] Salvo: teste_446_delta.json")