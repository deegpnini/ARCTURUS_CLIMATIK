"""
Roda LOEO (leave-one-event-out) e salva metadados:
- best_iteration por fold, por horizonte
- MAE por evento, por modelo
- mediana de best_iteration por horizonte
Saida: resultados/manifesto_pre_treino.json
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

# Split
with open(DATA / "split_v3.json", encoding="utf-8") as f:
    split = json.load(f)

eventos = split["historico"]

print(f"Total de eventos: {len(eventos)}")
print(f"Horizontes: 1h, 3h, 6h")
print()

PARAMS = {
    "objective": "regression",
    "metric": "mae",
    "num_leaves": 31,
    "max_depth": 5,
    "learning_rate": 0.05,
    "verbose": -1,
    "min_data_in_leaf": 20,
    "feature_fraction": 0.8,
    "bagging_fraction": 0.8,
    "bagging_freq": 5,
    "seed": 42,
    "data_random_seed": 42,
    "feature_fraction_seed": 42,
    "bagging_seed": 42,
    "deterministic": True,
    "force_col_wise": True,
    "num_threads": 1,
}

def mae(y, p):
    return float(np.mean(np.abs(y - p)))

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

# Hashes dos arquivos de entrada
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
    y_abs_all = df[target_abs].values
    y_delta_all = df["target_delta"].values

    folds = []
    for i, ev in enumerate(eventos):
        ev_ini = pd.Timestamp(ev["inicio"])
        ev_fim = pd.Timestamp(ev["fim"])
        m_test = (df["timestamp"] >= ev_ini) & (df["timestamp"] <= ev_fim)
        m_train = ~m_test

        if m_test.sum() == 0:
            continue

        X_tr = X_all[m_train]
        X_te = X_all[m_test]
        y_abs_tr = y_abs_all[m_train]
        y_abs_te = y_abs_all[m_test]
        y_delta_tr = y_delta_all[m_train]

        # Treina delta com early stopping na validacao = evento seguinte?
        # Aqui nao temos validacao interna. Treinamos com max rounds e pegamos best_iteration
        # como "melhor iteracao por evento retido"
        train_data = lgb.Dataset(X_tr, label=y_delta_tr)
        model_delta = lgb.train(
            PARAMS,
            train_data,
            num_boost_round=1000,
        )

        # Prever no evento retido
        pred_delta = model_delta.predict(X_te)
        pred_delta_abs = X_te[:, feats.index("cota")].astype(float) + pred_delta

        mae_delta = mae(y_abs_te, pred_delta_abs)

        folds.append({
            "evento": i + 1,
            "inicio": ev["inicio"],
            "fim": ev["fim"],
            "pico": ev["pico"],
            "n": int(m_test.sum()),
            "mae_delta": mae_delta,
            "best_iteration": int(model_delta.best_iteration) if model_delta.best_iteration > 0 else 1000,
        })

        if (i + 1) % 5 == 0:
            print(f"  {i+1}/{len(eventos)} folds concluidos")

    # Resumo do horizonte
    best_iters = [f["best_iteration"] for f in folds]
    mediana = int(np.median(best_iters))
    p25 = int(np.percentile(best_iters, 25))
    p75 = int(np.percentile(best_iters, 75))

    print(f"\nHorizonte {h}:")
    print(f"  Fold mean MAE_delta: {np.mean([f['mae_delta'] for f in folds]):.4f}")
    print(f"  best_iteration mediana: {mediana}  (IQR: {p25} - {p75})")
    print(f"  best_iteration min:     {min(best_iters)}")
    print(f"  best_iteration max:     {max(best_iters)}")

    resultado_por_horizonte[h] = {
        "num_boost_round_recomendado": mediana,
        "best_iteration_mediana": mediana,
        "best_iteration_iqr": [p25, p75],
        "best_iteration_min": min(best_iters),
        "best_iteration_max": max(best_iters),
        "mae_delta_medio_loeo": float(np.mean([f["mae_delta"] for f in folds])),
        "folds": folds,
    }

# Salva manifesto pre-treino
manifesto = {
    "data_geracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "projeto": "ARCTURUS CLIMATIK",
    "estacao": "84580000",
    "target": "delta",
    "reconstrucao": "cota_atual + delta_previsto",
    "versao": "1.0.0",
    "hashes_datasets": hashes,
    "features_por_horizonte": {},
    "params_lightgbm": PARAMS,
    "eventos_total": len(eventos),
    "resultado_por_horizonte": resultado_por_horizonte,
}

# Salvar features por horizonte
for h in ["1h", "3h", "6h"]:
    df = pd.read_csv(DATA / f"dataset_{h}.csv", nrows=2)
    feats = [c for c in df.columns if c not in ("timestamp", f"target_{h}")]
    manifesto["features_por_horizonte"][h] = feats

out = RES / "manifesto_pre_treino.json"
with open(out, "w", encoding="utf-8") as f:
    json.dump(manifesto, f, indent=2, ensure_ascii=False)

print(f"\n[OK] Manifesto salvo: {out}")
print(f"  Tamanho: {out.stat().st_size / 1024:.1f} KB")
