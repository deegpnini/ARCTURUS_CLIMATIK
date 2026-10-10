"""
LOEO v2 — leave-one-event-out com validacao interna temporal.

Protocolo:
- Retem 1 evento (teste externo)
- Nos 26 restantes, separa os 4 mais recentes como val interna
- Treina nos outros 22 (ou 21) com early stopping na val interna
- Captura best_iteration
- Avalia no evento retido (uma vez, sem reajustar)
- Salva best_iteration, MAE do teste externo, e metadados

Saida: resultados/manifesto_loeo_v2.json
"""
import os
import json
import hashlib
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path
from datetime import datetime

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
DATA = ROOT / "data"
RES = ROOT / "resultados"
RES.mkdir(exist_ok=True)

with open(DATA / "split_v3.json", encoding="utf-8") as f:
    split = json.load(f)

historico = split["historico"]
N_EV = len(historico)
N_VAL_INTERNA = 4  # protocolo do split original

print(f"Total de eventos: {N_EV}")
print(f"Val interna por fold: {N_VAL_INTERNA} eventos mais recentes")
print()

PARAMS = {
    "objective": "regression", "metric": "mae",
    "num_leaves": 31, "max_depth": 5, "learning_rate": 0.05,
    "verbose": -1, "min_data_in_leaf": 20,
    "feature_fraction": 0.8, "bagging_fraction": 0.8, "bagging_freq": 5,
    "seed": 42, "data_random_seed": 42, "feature_fraction_seed": 42, "bagging_seed": 42,
    "deterministic": True, "force_col_wise": True, "num_threads": 1,
}

MAX_ROUNDS = 2000  # aumentado pra evitar o teto anterior

def mae(y, p):
    return float(np.mean(np.abs(y - p)))

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

# Hashes
hashes = {}
for nome in ["split_v3.json", "dataset_1h.csv", "dataset_3h.csv", "dataset_6h.csv"]:
    p = DATA / nome
    if p.exists():
        hashes[nome] = sha256(p)
        print(f"  sha256 {nome}: {hashes[nome][:16]}...")
print()

resultado_por_horizonte = {}

for h in ["1h", "3h", "6h"]:
    print(f"\n{'='*70}")
    print(f"HORIZONTE {h}")
    print(f"{'='*70}")

    df = pd.read_csv(DATA / f"dataset_{h}.csv")
    target_abs = f"target_{h}"
    feats = [c for c in df.columns if c not in ("timestamp", target_abs)]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["target_delta"] = df[target_abs] - df["cota"]

    X_all = df[feats].values
    y_delta_all = df["target_delta"].values
    y_abs_all = df[target_abs].values
    ts_all = df["timestamp"].values

    idx_cota = feats.index("cota")
    folds = []

    for i, ev in enumerate(historico):
        ev_ini = pd.Timestamp(ev["inicio"])
        ev_fim = pd.Timestamp(ev["fim"])

        # Teste externo: evento i
        m_test_ext = (df["timestamp"] >= ev_ini) & (df["timestamp"] <= ev_fim)

        # Todos os OUTROS eventos disponiveis pra treino/val interna
        m_resto = ~m_test_ext
        idx_resto = np.where(m_resto)[0]

        if len(idx_resto) < 5:
            continue  # nao da pra separar val interna

        # Pega os 4 eventos mais recentes entre os restantes
        restantes_ev = [historico[j] for j in range(N_EV) if j != i]
        restantes_ev.sort(key=lambda e: e["fim"], reverse=True)
        val_evs = restantes_ev[:N_VAL_INTERNA]
        val_ini = min(pd.Timestamp(e["inicio"]) for e in val_evs)
        val_fim = max(pd.Timestamp(e["fim"]) for e in val_evs)

        m_val_int = (df["timestamp"] >= val_ini) & (df["timestamp"] <= val_fim) & m_resto
        m_tr_int = m_resto & ~m_val_int

        if m_tr_int.sum() < 100 or m_val_int.sum() < 50 or m_test_ext.sum() < 50:
            print(f"  fold {i+1}: poucos dados (tr={m_tr_int.sum()}, val={m_val_int.sum()}, te={m_test_ext.sum()}), pulando")
            continue

        X_tr = X_all[m_tr_int]
        y_tr = y_delta_all[m_tr_int]
        X_val = X_all[m_val_int]
        y_val = y_delta_all[m_val_int]

        train_data = lgb.Dataset(X_tr, label=y_tr)
        val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

        model = lgb.train(
            PARAMS,
            train_data,
            num_boost_round=MAX_ROUNDS,
            valid_sets=[val_data],
            callbacks=[lgb.early_stopping(50, verbose=False)],
        )

        best_iter = model.best_iteration if model.best_iteration > 0 else MAX_ROUNDS

        # Avaliacao externa no evento retido (uma vez, sem reajustar)
        X_te = X_all[m_test_ext]
        y_te_delta = y_delta_all[m_test_ext]
        y_te_abs = y_abs_all[m_test_ext]
        cota_te = X_all[m_test_ext][:, idx_cota].astype(float)

        pred_delta = model.predict(X_te, num_iteration=best_iter)
        pred_abs = cota_te + pred_delta

        mae_delta = mae(y_te_delta, pred_delta)
        mae_recon = mae(y_te_abs, pred_abs)

        folds.append({
            "evento_idx": i,
            "inicio": ev["inicio"],
            "fim": ev["fim"],
            "pico": ev["pico"],
            "n_treino": int(m_tr_int.sum()),
            "n_val": int(m_val_int.sum()),
            "n_teste": int(m_test_ext.sum()),
            "best_iteration": int(best_iter),
            "mae_delta": mae_delta,
            "mae_reconstrucao": mae_recon,
        })

        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{N_EV} folds concluidos")

    best_iters = [f["best_iteration"] for f in folds]
    maes_delta = [f["mae_delta"] for f in folds]

    mediana = int(np.median(best_iters))
    p25 = int(np.percentile(best_iters, 25))
    p75 = int(np.percentile(best_iters, 75))

    print(f"\nHorizonte {h}:")
    print(f"  Folds validos:           {len(folds)}")
    print(f"  MAE_delta medio:         {np.mean(maes_delta):.4f}")
    print(f"  MAE_delta mediano:       {np.median(maes_delta):.4f}")
    print(f"  best_iteration mediana:  {mediana}")
    print(f"  best_iteration IQR:      [{p25} - {p75}]")
    print(f"  best_iteration min/max:  {min(best_iters)} / {max(best_iters)}")

    resultado_por_horizonte[h] = {
        "num_boost_round_recomendado": mediana,
        "best_iteration_mediana": mediana,
        "best_iteration_iqr": [p25, p75],
        "best_iteration_min": min(best_iters),
        "best_iteration_max": max(best_iters),
        "mae_delta_medio_loeo": float(np.mean(maes_delta)),
        "mae_delta_mediano_loeo": float(np.median(maes_delta)),
        "folds": folds,
    }

manifesto = {
    "data_geracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "projeto": "ARCTURUS CLIMATIK",
    "versao": "2.0.0",
    "protocolo": "LOEO com validacao interna temporal (4 eventos mais recentes)",
    "hashes_datasets": hashes,
    "params_lightgbm": PARAMS,
    "max_rounds_busca": MAX_ROUNDS,
    "n_boost_round_regra": "mediana dos best_iteration dos 27 folds",
    "resultado_por_horizonte": resultado_por_horizonte,
}

out = RES / "manifesto_loeo_v2.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(manifesto, f, indent=2, ensure_ascii=False)

print(f"\n[OK] Manifesto salvo: {out}")
print(f"  Tamanho: {out.stat().st_size / 1024:.1f} KB")
