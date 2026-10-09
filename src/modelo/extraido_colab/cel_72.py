# ============================================================
# SHADOW MODE — ARCTURUS_FORECAST
# Roda previsao + registra log
# (roda no Colab por enquanto)
# ============================================================
import pandas as pd
import numpy as np
import json
import lightgbm as lgb
from datetime import datetime
import os

# ============================================================
# 1. CARREGA MODELOS TREINADOS (se nao tem, treina)
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
    print(f"Modelo {h} OK (iter={model.best_iteration})")

# ============================================================
# 2. FAZ PREVISAO COM DADO NOVO (exemplo: ultima cota do evento)
# ============================================================
# Em producao, isso viria do ana_auth + endpoint.
# Aqui, simula com dados ja carregados.

# Ultima leitura do evento
with open("/content/telemetria_84580000_2026.json") as f:
    tel = json.load(f)

# Cota atual = 361 cm (ultima leitura em 22/09 08:45)
COTA_ATUAL = 361.0
TIMESTAMP = "2026-09-22 08:45:00"

# Para features, precisamos do dataset reconstruido
# Simplificacao: usar features vazias (so cota)
feature_dict = {
    'cota': COTA_ATUAL,
    # ... resto None
}
for f in ['vazao', 'cota_lag_15m', 'cota_lag_30m', 'cota_lag_60m',
          'cota_lag_180m', 'cota_lag_360m', 'cota_lag_720m', 'cota_lag_1440m',
          'delta_15m', 'delta_60m', 'delta_180m', 'aceleracao_1h',
          'cota_std_12h', 'cota_max_12h', 'cota_min_12h',
          'chuva_15m', 'chuva_60m', 'chuva_180m', 'chuva_360m',
          'chuva_720m', 'chuva_1440m', 'chuva_2880m',
          'sin_hora', 'cos_hora', 'sin_dia_ano', 'cos_dia_ano']:
    feature_dict.setdefault(f, None)

# ============================================================
# 3. REGISTRA NO LOG
# ============================================================
LOG_PATH = "/content/drive/MyDrive/ARCTURUS_ML/shadow_log.jsonl"

previsoes = {}
for h in ['1h', '3h', '6h']:
    m = modelos[h]
    X_pred = np.array([[feature_dict.get(f) for f in m['feats']]], dtype=object)
    delta_pred = float(m['model'].predict(X_pred)[0])
    cota_pred = COTA_ATUAL + delta_pred
    previsoes[h] = {
        'delta': delta_pred,
        'cota': cota_pred,
    }

log_entry = {
    'timestamp': datetime.now().isoformat(),
    'cota_atual': COTA_ATUAL,
    'data_medicao': TIMESTAMP,
    'previsoes': previsoes,
    'features_disponiveis': sum(1 for v in feature_dict.values() if v is not None),
    'features_total': len(feature_dict),
    'modelo_version': 'v1.0',
}

# Append ao log
with open(LOG_PATH, 'a') as f:
    f.write(json.dumps(log_entry, default=str) + '\n')

print("\n=== SHADOW MODE ===")
print(f"Cota atual: {COTA_ATUAL} cm")
print(f"Features: {log_entry['features_disponiveis']}/{log_entry['features_total']}")
print()
for h in ['1h', '3h', '6h']:
    p = previsoes[h]
    print(f"{h}: delta={p['delta']:+.1f} | cota={p['cota']:.1f}")
print()
print(f"Log: {LOG_PATH}")