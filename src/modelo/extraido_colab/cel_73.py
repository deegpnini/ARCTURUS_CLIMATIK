# ============================================================
# SHADOW MODE REAL — features reconstruidas
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb
from datetime import datetime, timedelta

# ============================================================
# 1. TREINA MODELOS (usa dataset atual)
# ============================================================
with open("/content/split_v3.json") as f:
    split = json.load(f)

treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']

modelos = {}
for h in ['1h', '3h', '6h']:
    df = pd.read_csv(f"/content/dataset_{h}.csv")
    target_abs = f'target_{h}'
    feats = [c for c in df.columns if c not in ('timestamp', target_abs)]
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    df['target_delta'] = df[target_abs] - df['cota']

    m_tr = df['timestamp'] <= treino_fim
    m_va = (df['timestamp'] >= val_ini) & (df['timestamp'] <= val_fim)

    X = df[feats].values
    y_delta = df['target_delta'].values

    params = {
        'objective': 'regression', 'metric': 'mae',
        'num_leaves': 31, 'max_depth': 5,
        'learning_rate': 0.05, 'verbose': -1,
        'min_data_in_leaf': 20,
        'feature_fraction': 0.8, 'bagging_fraction': 0.8, 'bagging_freq': 5,
    }

    train_data = lgb.Dataset(X[m_tr], label=y_delta[m_tr])
    val_data = lgb.Dataset(X[m_va], label=y_delta[m_va], reference=train_data)
    model = lgb.train(params, train_data, num_boost_round=1000,
                      valid_sets=[val_data],
                      callbacks=[lgb.early_stopping(50, verbose=False)])

    modelos[h] = {'model': model, 'feats': feats}

print("Modelos treinados\n")

# ============================================================
# 2. CARREGA TELEMETRIA (ultimas 48h)
# ============================================================
with open("/content/telemetria_84580000_2026.json") as f:
    tel = json.load(f)

# Mapa de cota e chuva por timestamp
dados = {}
for it in tel['items']:
    ts = it.get('Data_Hora_Medicao', '')[:19]
    c = it.get('Cota_Adotada')
    ch = it.get('Chuva_Adotada')
    v = it.get('Vazao_Adotada')

    def num(x):
        if x is None or x == '': return None
        try: return float(str(x).replace(',', '.'))
        except: return None

    dados[ts] = {
        'cota': num(c),
        'chuva': num(ch),
        'vazao': num(v),
    }

# ============================================================
# 3. RECONSTROI FEATURES PARA UM TIMESTAMP ALVO
# ============================================================
def cota_em(ts):
    d = dados.get(ts)
    return d['cota'] if d else None

def chuva_soma(ts_ref, minutos):
    dt = datetime.strptime(ts_ref, "%Y-%m-%d %H:%M:%S")
    total = 0
    validos = 0
    n = minutos // 15 + 1
    for i in range(n):
        t = (dt - timedelta(minutes=15*i)).strftime("%Y-%m-%d %H:%M:%S")
        d = dados.get(t)
        if d and d['chuva'] is not None:
            total += d['chuva']
            validos += 1
    if validos / n < 0.9:
        return None
    return total

def reconstruir_features(ts_alvo):
    """Reconstroi features no timestamp alvo."""
    dt = datetime.strptime(ts_alvo, "%Y-%m-%d %H:%M:%S")

    def ts_minus(min):
        return (dt - timedelta(minutes=min)).strftime("%Y-%m-%d %H:%M:%S")

    cota_atual = cota_em(ts_alvo)
    if cota_atual is None:
        return None

    f = {
        'cota': cota_atual,
        'vazao': dados.get(ts_alvo, {}).get('vazao'),
        'cota_lag_15m': cota_em(ts_minus(15)),
        'cota_lag_30m': cota_em(ts_minus(30)),
        'cota_lag_60m': cota_em(ts_minus(60)),
        'cota_lag_180m': cota_em(ts_minus(180)),
        'cota_lag_360m': cota_em(ts_minus(360)),
        'cota_lag_720m': cota_em(ts_minus(720)),
        'cota_lag_1440m': cota_em(ts_minus(1440)),
    }

    # Deltas
    for lag in [15, 60, 180]:
        v = f.get(f'cota_lag_{lag}m')
        f[f'delta_{lag}m'] = (cota_atual - v) if v is not None else None

    # Aceleracao
    d60 = f.get('delta_60m')
    d60_prev = None
    c_prev = cota_em(ts_minus(60))
    if c_prev is not None:
        c_prev_prev = cota_em(ts_minus(120))
        if c_prev_prev is not None:
            d60_prev = c_prev - c_prev_prev
    f['aceleracao_1h'] = (d60 - d60_prev) if (d60 is not None and d60_prev is not None) else None

    # Stats 12h
    # (simplificado - so conta validos)
    f['cota_std_12h'] = None  # TODO
    f['cota_max_12h'] = None
    f['cota_min_12h'] = None

    # Chuvas
    f['chuva_15m'] = chuva_soma(ts_alvo, 15)
    f['chuva_60m'] = chuva_soma(ts_alvo, 60)
    f['chuva_180m'] = chuva_soma(ts_alvo, 180)
    f['chuva_360m'] = chuva_soma(ts_alvo, 360)
    f['chuva_720m'] = chuva_soma(ts_alvo, 720)
    f['chuva_1440m'] = chuva_soma(ts_alvo, 1440)
    f['chuva_2880m'] = chuva_soma(ts_alvo, 2880)

    # Cíclicos
    hora = dt.hour + dt.minute / 60
    dia_ano = dt.timetuple().tm_yday
    f['sin_hora'] = np.sin(2 * np.pi * hora / 24)
    f['cos_hora'] = np.cos(2 * np.pi * hora / 24)
    f['sin_dia_ano'] = np.sin(2 * np.pi * dia_ano / 365)
    f['cos_dia_ano'] = np.cos(2 * np.pi * dia_ano / 365)

    return f

# ============================================================
# 4. FAZ PREVISAO REAL
# ============================================================
TS_ATUAL = "2026-09-22 08:45:00"
feats_dict = reconstruir_features(TS_ATUAL)

if feats_dict is None:
    print("ERRO: cota atual indisponivel")
else:
    print("=== SHADOW MODE REAL ===")
    print(f"Timestamp: {TS_ATUAL}")
    print(f"Cota atual: {feats_dict['cota']} cm")
    print()

    disponiveis = sum(1 for v in feats_dict.values() if v is not None)
    print(f"Features disponiveis: {disponiveis}/{len(feats_dict)}")
    print()

    previsoes = {}
    for h in ['1h', '3h', '6h']:
        m = modelos[h]
        X_pred = np.array([[feats_dict.get(f) for f in m['feats']]], dtype=object)
        delta_pred = float(m['model'].predict(X_pred)[0])
        cota_pred = feats_dict['cota'] + delta_pred
        previsoes[h] = {'delta': delta_pred, 'cota': cota_pred}
        print(f"{h}: delta={delta_pred:+.1f} | cota={cota_pred:.1f}")

    # Salva no log
    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'data_medicao': TS_ATUAL,
        'cota_atual': feats_dict['cota'],
        'previsoes': previsoes,
        'features_disponiveis': disponiveis,
        'features_total': len(feats_dict),
        'modelo_version': 'v1.0',
    }
    LOG = "/content/drive/MyDrive/ARCTURUS_ML/shadow_log.jsonl"
    with open(LOG, 'a') as f:
        f.write(json.dumps(log_entry, default=str) + '\n')
    print(f"\nLog: {LOG}")