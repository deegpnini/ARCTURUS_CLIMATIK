# ============================================================
# C — TESTE DE GENERALIZACAO: input 446 como feature
# Alvo: recessao subsequente (01:00, 03:00, 06:00)
# Modelo congelado. Sem interpolar gap. Sem ajustar.
# ============================================================
import pandas as pd
import numpy as np
import json
import os
import lightgbm as lgb

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

# Mapa de leituras 21-22/09
leituras = {}
for it in tel['items']:
    ts = it.get('Data_Hora_Medicao', '')[:19]
    if not ts.startswith(('2026-09-21', '2026-09-22')):
        continue
    cota = it.get('Cota_Adotada')
    v = None
    if cota and cota not in ('', '0.00'):
        try: v = float(str(cota).replace(',', '.'))
        except: pass
    leituras[ts] = {
        'cota': v,
        'chuva': None,
        'vazao': None,
    }
    ch = it.get('Chuva_Adotada')
    if ch and ch != '0.00':
        try: leituras[ts]['chuva'] = float(str(ch).replace(',', '.'))
        except: pass
    va = it.get('Vazao_Adotada')
    if va and va not in ('', '0.00'):
        try: leituras[ts]['vazao'] = float(str(va).replace(',', '.'))
        except: pass

print(f"Leituras disponiveis: {len(leituras)}")

# ============================================================
# 2. INSTANTE ALVO — 22/09/2026 00:00
# ============================================================
T0 = "2026-09-22 00:00:00"
COTA_T0 = 446.0
print(f"\nInstante alvo: {T0} (cota {COTA_T0} cm)")
print(f"Gap a esquerda: 20:45 -> 00:00 (195 min)")

# ============================================================
# 3. FEATURES DISPONIVEIS EM T0?
# ============================================================
# Features que dependem de lags:
#   - cota_lag_15m = cota(t-15min)  = cota(23:45) -> GAP -> INDISPONIVEL
#   - cota_lag_30m = cota(t-30min)  = cota(23:30) -> GAP
#   - cota_lag_60m = cota(t-1h)     = cota(23:00) -> GAP
#   - cota_lag_180m = cota(t-3h)    = cota(21:00) -> GAP
#   - cota_lag_360m = cota(t-6h)    = cota(18:00) -> DISPONIVEL
#   - cota_lag_720m = cota(t-12h)   = cota(12:00) -> DISPONIVEL
#   - cota_lag_1440m = cota(t-24h)  = cota(00:00 do dia 21) -> DISPONIVEL
#
# Entao: features com lag <= 3h = INDISPONIVEIS
#        features com lag >= 6h = DISPONIVEIS

# ============================================================
# 4. TREINA 3 MODELOS (modelo congelado)
# ============================================================
modelos = {}
for h in ['1h', '3h', '6h']:
    print(f"\nTreinando modelo {h}...")
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

    modelos[h] = {'model': model, 'feats': feats}
    print(f"  best_iter={model.best_iteration}")

# ============================================================
# 5. MONTA FEATURES EM T0 (00:00)
# ============================================================
# Usa SÓ features disponíveis.
# Para features indisponíveis -> NaN (LightGBM lida)

print("\n" + "="*80)
print("CONSTRUINDO FEATURES EM T0")
print("="*80)

def get_cota(ts):
    """Retorna cota em ts (YYYY-MM-DD HH:MM:SS) ou None."""
    r = leituras.get(ts)
    return r['cota'] if r else None

def chuva_janela(ts_ref, minutos):
    """Soma chuva na janela [ts_ref - minutos, ts_ref]."""
    from datetime import datetime, timedelta
    dt_ref = datetime.strptime(ts_ref, "%Y-%m-%d %H:%M:%S")
    total = 0
    validos = 0
    n_esperado = minutos // 15 + 1
    for i in range(n_esperado):
        dt = dt_ref - timedelta(minutes=15*i)
        ts = dt.strftime("%Y-%m-%d %H:%M:%S")
        r = leituras.get(ts)
        if r and r['chuva'] is not None:
            total += r['chuva']
            validos += 1
    if validos / n_esperado < 0.9:
        return None
    return total

def cota_lag(ts_ref, minutos):
    from datetime import datetime, timedelta
    dt = datetime.strptime(ts_ref, "%Y-%m-%d %H:%M:%S") - timedelta(minutes=minutos)
    return get_cota(dt.strftime("%Y-%m-%d %H:%M:%S"))

# Constroi feature vector para cada horizonte
# Mas as features sao as MESMAS em T0. So muda qual modelo aplica.

cota_t = 446.0

feats_dict = {
    'cota': cota_t,
    'vazao': None,  # disponivel em T0? nao temos leitura
    # lags
    'cota_lag_15m': cota_lag(T0, 15),    # 23:45 -> GAP
    'cota_lag_30m': cota_lag(T0, 30),    # 23:30 -> GAP
    'cota_lag_60m': cota_lag(T0, 60),    # 23:00 -> GAP
    'cota_lag_180m': cota_lag(T0, 180),  # 21:00 -> GAP
    'cota_lag_360m': cota_lag(T0, 360),  # 18:00 -> DISPONIVEL
    'cota_lag_720m': cota_lag(T0, 720),  # 12:00 -> DISPONIVEL
    'cota_lag_1440m': cota_lag(T0, 1440),# 00:00 -> DISPONIVEL
    # deltas (dependem de lag)
    'delta_15m': None,  # precisa lag_15m -> GAP
    'delta_60m': None,  # GAP
    'delta_180m': None, # GAP
    'aceleracao_1h': None, # GAP
    # stats 12h
    'cota_std_12h': None,  # janela 12h inclui gap
    'cota_max_12h': None,
    'cota_min_12h': None,
    # chuva (janelas que incluem gap -> None)
    'chuva_15m': None,   # 23:45 -> GAP
    'chuva_60m': None,   # 23:00 -> GAP
    'chuva_180m': None,  # 21:00 -> GAP
    'chuva_360m': chuva_janela(T0, 360),  # 18:00 -> DISPONIVEL
    'chuva_720m': chuva_janela(T0, 720),  # 12:00 -> DISPONIVEL
    'chuva_1440m': chuva_janela(T0, 1440),# 00:00 -> DISPONIVEL
    'chuva_2880m': chuva_janela(T0, 2880),# 2 dias
}

print(f"\nFeatures:")
for k, v in feats_dict.items():
    status = "DISPONIVEL" if v is not None else "INDISPONIVEL"
    print(f"  {k:20s}: {str(v):15s} [{status}]")

# ============================================================
# 6. PREDIZ COM CADA MODELO
# ============================================================
# Alvos observados
ALVOS = {
    '1h': ('2026-09-22 01:00:00', 424.0),
    '3h': ('2026-09-22 03:00:00', 413.0),
    '6h': ('2026-09-22 06:00:00', 375.0),
}

print("\n" + "="*80)
print("PREDICOES EM T0 = 22/09 00:00 (cota 446 cm)")
print("="*80)
print(f"\n{'H':4s} | {'Alvo':6s} | {'Obs':6s} | {'Persist':9s} | {'LightGBM':9s} | {'Erro_pers':10s} | {'Erro_lgb':10s}")
print("-"*80)

resultados_c = {}
for h in ['1h', '3h', '6h']:
    modelo_h = modelos[h]
    feats_h = modelo_h['feats']
    model = modelo_h['model']

    # Monta X para o modelo (na ordem das features)
    X_pred = []
    for f in feats_h:
        v = feats_dict.get(f)
        X_pred.append(v)
    X_pred = np.array([X_pred], dtype=object)

    pred = float(model.predict(X_pred)[0])

    alvo_ts, alvo_obs = ALVOS[h]

    # Persistencia: pred = cota_t (446)
    persist = 446.0

    err_pers = abs(persist - alvo_obs)
    err_lgb = abs(pred - alvo_obs)

    print(f"{h:4s} | {alvo_ts[11:16]:6s} | {alvo_obs:6.0f} | {persist:9.0f} | {pred:9.2f} | {err_pers:10.2f} | {err_lgb:10.2f}")

    resultados_c[h] = {
        'alvo_ts': alvo_ts,
        'alvo_obs': alvo_obs,
        'persist': persist,
        'pred_lgb': pred,
        'erro_persist': err_pers,
        'erro_lgb': err_lgb,
        'features_disponiveis': sum(1 for f in feats_h if feats_dict.get(f) is not None),
        'features_total': len(feats_h),
    }

# ============================================================
# 7. TABELA DE DISPONIBILIDADE
# ============================================================
print("\n" + "="*80)
print("TABELA DE DISPONIBILIDADE DE FEATURES EM T0")
print("="*80)
print(f"{'Feature':25s} | {'Valor':15s} | {'Status':15s}")
print("-"*80)
for k, v in feats_dict.items():
    status = "DISPONIVEL" if v is not None else "INDISPONIVEL (gap)"
    val = f"{v:.2f}" if isinstance(v, (int, float)) else str(v)
    print(f"{k:25s} | {val:15s} | {status:15s}")

# ============================================================
# 8. RESUMO E SALVA
# ============================================================
print("\n" + "="*80)
print("RESUMO")
print("="*80)
for h in ['1h', '3h', '6h']:
    r = resultados_c[h]
    print(f"{h}: obs={r['alvo_obs']:.0f} | persist={r['persist']:.0f} | lgb={r['pred_lgb']:.1f} | err_lgb={r['erro_lgb']:.1f}")

# Salva
with open("/content/drive/MyDrive/ARCTURUS_ML/resultado_teste_c.json", 'w') as f:
    json.dump(resultados_c, f, indent=2, default=str)
print(f"\n[OK] Salvo: /content/drive/MyDrive/ARCTURUS_ML/resultado_teste_c.json")