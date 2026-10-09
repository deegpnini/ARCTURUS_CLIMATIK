# ============================================================
# B — EXTRAPOLACAO OPERACIONAL 21-22/09/2026
# Auto-carrega do Drive. Modelo congelado. 446 fora do treino.
# ============================================================
import pandas as pd
import numpy as np
import json
import os
import shutil
import lightgbm as lgb

# ============================================================
# 1. MONTA DRIVE + AUTO-CARREGA
# ============================================================
from google.colab import drive
drive.mount('/content/drive')

DRIVE = '/content/drive/MyDrive'
PASTA = f"{DRIVE}/ARCTURUS_ML"

print(f"Procurando em: {PASTA}")
if not os.path.exists(PASTA):
    raise SystemExit(f"[!] Pasta {PASTA} nao existe")

print("Conteudo da pasta:")
for f in os.listdir(PASTA):
    print(f"  - {f}")

ARQUIVOS = [
    "dataset_1h.csv",
    "dataset_3h.csv",
    "dataset_6h.csv",
    "split_v3.json",
    "telemetria_84580000_2026.json",
]

print()
for nome in ARQUIVOS:
    origem = f"{PASTA}/{nome}"
    if os.path.exists(origem):
        shutil.copy2(origem, f"/content/{nome}")
        print(f"[OK] {nome} copiado")
    else:
        raise SystemExit(f"[!] FALTA: {nome}")

# ============================================================
# 2. CARREGA SPLIT
# ============================================================
with open("/content/split_v3.json") as f:
    split = json.load(f)

treino_fim = split['historico'][17]['fim']
val_ini = split['historico'][18]['inicio']
val_fim = split['historico'][21]['fim']

print(f"\nSplit carregado:")
print(f"  Treino: <= {treino_fim}")
print(f"  Val:    {val_ini} a {val_fim}")
print(f"  Eventos teste: {len(split['historico'][22:27])}")

# ============================================================
# 3. CARREGA TELEMETRIA E MARCA GAP
# ============================================================
with open("/content/telemetria_84580000_2026.json") as f:
    tel = json.load(f)

evento = [it for it in tel['items']
          if it.get('Data_Hora_Medicao', '').startswith(('2026-09-21', '2026-09-22'))]
evento.sort(key=lambda x: x.get('Data_Hora_Medicao'))

print(f"\nLeituras do evento 21-22/09: {len(evento)}")

# Mapa de timestamps
timestamps = {}
for it in evento:
    ts = it.get('Data_Hora_Medicao', '')[:19]
    cota = it.get('Cota_Adotada')
    v = None
    if cota and cota not in ('', '0.00'):
        try: v = float(str(cota).replace(',', '.'))
        except: pass
    timestamps[ts] = v

n_validos = sum(1 for v in timestamps.values() if v is not None)
n_nulos = sum(1 for v in timestamps.values() if v is None)
print(f"  Validos: {n_validos}")
print(f"  Nulos: {n_nulos}")
print(f"  GAP oficial: 2026-09-21 20:45 -> 2026-09-22 00:00 (195 min)")

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
    print(f"  Modelo {h} pronto (best_iter={model.best_iteration})")

# ============================================================
# 5. FILTRA FEATURES DO EVENTO
# ============================================================
print("\n" + "="*80)
print("FILTRANDO FEATURES DO EVENTO 21-22/09")
print("="*80)

eventos_features = {}
for h in ['1h', '3h', '6h']:
    df = pd.read_csv(f"/content/dataset_{h}.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    m_ev = (df['timestamp'] >= "2026-09-21") & (df['timestamp'] <= "2026-09-22 23:59:59")
    df_ev = df[m_ev].copy()
    eventos_features[h] = df_ev
    print(f"  {h}: {len(df_ev)} linhas")

# ============================================================
# 6. PREDIZ E COMPARA
# ============================================================
print("\n" + "="*80)
print("PREDICOES DO EVENTO 21-22/09")
print("="*80)

resultados = {}

for h in ['1h', '3h', '6h']:
    df_ev = eventos_features[h]
    if len(df_ev) == 0:
        print(f"\n{h}: sem linhas")
        continue

    target = f'target_{h}'
    feats = modelos[h]['feats']
    model = modelos[h]['model']

    df_val = df_ev.dropna(subset=[target]).copy()
    if len(df_val) == 0:
        print(f"\n{h}: sem target observado")
        continue

    X_ev = df_val[feats].values
    y_ev = df_val[target].values
    pred_ev = model.predict(X_ev)

    idx_cota = feats.index('cota')
    persist_ev = X_ev[:, idx_cota].astype(float)

    mae_pers = float(np.mean(np.abs(y_ev - persist_ev)))
    mae_lgb = float(np.mean(np.abs(y_ev - pred_ev)))
    erro_max = float(np.max(np.abs(y_ev - pred_ev)))

    mask_pico = y_ev > 312
    if mask_pico.sum() > 0:
        mae_pico = float(np.mean(np.abs(y_ev[mask_pico] - pred_ev[mask_pico])))
        n_pico = int(mask_pico.sum())
    else:
        mae_pico = None
        n_pico = 0

    pred_max = float(np.max(pred_ev))
    y_max = float(np.max(y_ev))
    n_pred_312 = int((pred_ev > 312).sum())
    n_obs_312 = int((y_ev > 312).sum())

    print(f"\n=== {h} ===")
    print(f"  Linhas validas: {len(df_val)}")
    print(f"  MAE persist: {mae_pers:.2f}")
    print(f"  MAE LightGBM: {mae_lgb:.2f}")
    print(f"  Erro maximo LGB: {erro_max:.2f}")
    if mae_pico:
        print(f"  MAE no pico (>312): {mae_pico:.2f} (n={n_pico})")
    else:
        print(f"  Sem obs > 312 no teste")
    print(f"  Previsao maxima: {pred_max:.2f}")
    print(f"  Observado maximo: {y_max:.2f}")
    print(f"  Previsoes > 312: {n_pred_312}")
    print(f"  Observacoes > 312: {n_obs_312}")

    resultados[h] = {
        'n': len(df_val),
        'mae_pers': mae_pers,
        'mae_lgb': mae_lgb,
        'erro_max': erro_max,
        'mae_pico': mae_pico,
        'n_pico': n_pico,
        'pred_max': pred_max,
        'y_max': y_max,
        'n_pred_312': n_pred_312,
        'n_obs_312': n_obs_312,
    }

# ============================================================
# 7. RESUMO
# ============================================================
print("\n" + "="*80)
print("RESUMO EXTRAPOLACAO")
print("="*80)
print(f"{'H':4s} | {'N':6s} | {'MAE_pers':10s} | {'MAE_lgb':10s} | {'Delta':8s} | {'Pred_max':10s} | {'Obs_max':10s}")
print("-"*80)
for h in ['1h', '3h', '6h']:
    if h not in resultados: continue
    r = resultados[h]
    delta = r['mae_pers'] - r['mae_lgb']
    print(f"{h:4s} | {r['n']:6d} | {r['mae_pers']:10.2f} | {r['mae_lgb']:10.2f} | {delta:+8.2f} | {r['pred_max']:10.2f} | {r['y_max']:10.2f}")

print()
print("INTERPRETACAO:")
print("  pred_max ~ obs_max: extrapolou bem")
print("  pred_max << obs_max: nao extrapola")
print("  n_pred_312 << n_obs_312: nao preve extremos")

# ============================================================
# 8. SALVA NO DRIVE
# ============================================================
with open(f"{PASTA}/resultado_extrapolacao.json", 'w') as f:
    json.dump(resultados, f, indent=2, default=str)
print(f"\n[OK] Salvo: {PASTA}/resultado_extrapolacao.json")