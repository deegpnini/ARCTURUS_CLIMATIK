# ============================================================
# B — EXTRAPOLACAO OPERACIONAL 21-22/09/2026
# Auto-carrega arquivos do Google Drive (sem upload manual)
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
drive.mount('/content/drive', force_remount=False)

DRIVE = '/content/drive/MyDrive'
PASTA = f"{DRIVE}/ARCTURUS_ML"

# Lista o que tem na pasta
if not os.path.exists(PASTA):
    print(f"[!] Pasta {PASTA} nao existe. Faz upload primeiro.")
else:
    print(f"[OK] Pasta {PASTA} encontrada.")
    print("Conteudo:")
    for f in os.listdir(PASTA):
        print(f"  - {f}")

# Arquivos necessarios
ARQUIVOS = ["dataset_1h.csv", "dataset_3h.csv", "dataset_6h.csv", "split_v3.json"]

# Copia do Drive para /content/
for nome in ARQUIVOS:
    origem = f"{PASTA}/{nome}"
    if os.path.exists(origem):
        shutil.copy2(origem, f"/content/{nome}")
        print(f"[OK] {nome} copiado")
    else:
        print(f"[!] FALTA: {nome}")

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
# 3. CARREGA TELEMETRIA 2026 (evento 21-22/09)
# ============================================================
# Busca o arquivo telemetria_84580000_2026.json no Drive
# (pode estar em ARCTURUS_ML ou outro lugar)
TELEMETRIA_NOME = "telemetria_84580000_2026.json"

telemetria_path = None
for root, dirs, files in os.walk(DRIVE):
    if TELEMETRIA_NOME in files:
        telemetria_path = os.path.join(root, TELEMETRIA_NOME)
        break

if telemetria_path is None:
    print(f"\n[!] {TELEMETRIA_NOME} nao encontrado no Drive.")
    print("Faz upload dele primeiro (ou copia pra ARCTURUS_ML).")
    # Pausa aqui
    raise SystemExit("Falta telemetria")

print(f"\n[OK] Telemetria encontrada: {telemetria_path}")
shutil.copy2(telemetria_path, f"/content/{TELEMETRIA_NOME}")

with open(f"/content/{TELEMETRIA_NOME}") as f:
    tel = json.load(f)

# Filtra evento 21-22/09
evento = [it for it in tel['items']
          if it.get('Data_Hora_Medicao', '').startswith(('2026-09-21', '2026-09-22'))]
evento.sort(key=lambda x: x.get('Data_Hora_Medicao'))

print(f"Leituras do evento: {len(evento)}")

# ============================================================
# 4. TREINA 3 MODELOS
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

# ============================================================
# 5. FILTRA FEATURES DO EVENTO
# ============================================================
eventos_features = {}
for h in ['1h', '3h', '6h']:
    df = pd.read_csv(f"/content/dataset_{h}.csv")
    df['timestamp'] = pd.to_datetime(df['timestamp'])
    m_ev = (df['timestamp'] >= "2026-09-21") & (df['timestamp'] <= "2026-09-22 23:59:59")
    df_ev = df[m_ev].copy()
    eventos_features[h] = df_ev
    print(f"\n{h}: {len(df_ev)} linhas de features do evento")

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

# Salva resultado no Drive
with open(f"{PASTA}/resultado_extrapolacao.json", 'w') as f:
    json.dump(resultados, f, indent=2, default=str)
print(f"\n[OK] Salvo em {PASTA}/resultado_extrapolacao.json")