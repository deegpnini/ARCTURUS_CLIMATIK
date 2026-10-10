"""
Treina modelo de PRODUCAO com todos os 27 eventos.
Usa num_boost_round = mediana do LOEO v2 (156 / 84 / 74).
Salva modelo NATIVO (Booster.save_model) + manifesto de producao.

NAO faz early stopping (nao tem validacao propria).
NAO avalia no teste (teste e intocado desde o LOEO).

Saida:
  modelos/modelo_delta_1h.txt
  modelos/modelo_delta_3h.txt
  modelos/modelo_delta_6h.txt
  modelos/manifesto_producao.json
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
MODELOS = ROOT / "modelos"
MODELOS.mkdir(exist_ok=True)

# ============================================================
# 1. Carrega manifesto LOEO v2 (tem os num_boost_round)
# ============================================================
with open(RES / "manifesto_loeo_v2.json", encoding="utf-8-sig") as f:
    loeo = json.load(f)

print("=" * 70)
print("  ARCTURUS — Treino do modelo de PRODUCAO")
print("=" * 70)
print()
print("Medianas do LOEO (num_boost_round):")
for h, d in loeo["resultado_por_horizonte"].items():
    print(f"  {h}: {d['best_iteration_mediana']} rounds")
print()

# ============================================================
# 2. Carrega split
# ============================================================
with open(DATA / "split_v3.json", encoding="utf-8") as f:
    split = json.load(f)

historico = split["historico"]
operacional = split["operacional"]

# Todos os 27 eventos historicos + o operacional
# O evento operacional entra no treino? Decisao:
# - NAO usar o operacional (fica intocado pra futura validacao)
# - Usar apenas os 27 eventos historicos
print(f"Eventos para treino: {len(historico)} (historicos)")
print(f"Evento operacional reservado: {len(operacional)}")
print()

# ============================================================
# 3. Params do LightGBM (identicos ao LOEO)
# ============================================================
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

# ============================================================
# 4. Calcula hash dos arquivos de entrada
# ============================================================
def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

hashes = {}
for nome in ["split_v3.json", "dataset_1h.csv", "dataset_3h.csv", "dataset_6h.csv"]:
    p = DATA / nome
    if p.exists():
        hashes[nome] = sha256(p)
        print(f"  sha256 {nome}: {hashes[nome][:16]}...")
print()

# ============================================================
# 5. Treina um modelo por horizonte
# ============================================================
manifesto_prod = {
    "data_geracao": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    "projeto": "ARCTURUS CLIMATIK",
    "versao": "1.0.0",
    "status": "PRODUCAO",
    "estacao": "84580000",
    "target": "delta",
    "reconstrucao": "cota_atual + delta_previsto",
    "referencia_loeo": "resultados/manifesto_loeo_v2.json",
    "hashes_datasets": hashes,
    "params_lightgbm": PARAMS,
    "horizontes": {},
}

for h in ["1h", "3h", "6h"]:
    print(f"{'='*70}")
    print(f"HORIZONTE {h}")
    print(f"{'='*70}")

    n_rounds = loeo["resultado_por_horizonte"][h]["best_iteration_mediana"]
    print(f"  num_boost_round: {n_rounds} (mediana do LOEO)")

    # Carrega dados
    df = pd.read_csv(DATA / f"dataset_{h}.csv")
    target_abs = f"target_{h}"
    feats = [c for c in df.columns if c not in ("timestamp", target_abs, "vazao")]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["target_delta"] = df[target_abs] - df["cota"]

    # Filtra apenas linhas com target valido (o modelo nao pode treinar em NaN)
    mask_valido = df["target_delta"].notna()
    df_train = df[mask_valido].copy()

    X = df_train[feats].values
    y = df_train["target_delta"].values

    print(f"  Linhas de treino: {len(X)} (de {len(df)} totais)")
    print(f"  Features: {len(feats)}")

    # Treina (sem early stopping, sem validacao)
    train_data = lgb.Dataset(X, label=y)
    model = lgb.train(
        PARAMS,
        train_data,
        num_boost_round=n_rounds,
    )

    # Salva no formato NATIVO (mais seguro que joblib)
    model_path = MODELOS / f"modelo_delta_{h}.txt"
    model.save_model(str(model_path))
    model_hash = sha256(model_path)
    print(f"  [OK] {model_path.name} ({model_path.stat().st_size / 1024:.1f} KB)")
    print(f"       sha256: {model_hash[:16]}...")

    # Assinatura de reprodutibilidade: preve a ULTIMA linha do treino
    amostra = X[-1:]
    pred_amostra = float(model.predict(amostra)[0])
    print(f"  Assinatura: predicao da ultima linha = {pred_amostra:.6f}")

    manifesto_prod["horizontes"][h] = {
        "arquivo": model_path.name,
        "num_boost_round": n_rounds,
        "n_linhas_treino": int(len(X)),
        "n_features": len(feats),
        "features": feats,
        "sha256_modelo": model_hash,
        "assinatura_reprodutibilidade": {
            "amostra": "ultima linha do dataset filtrado por target valido",
            "valor_esperado": pred_amostra,
        },
    }

    print()

# ============================================================
# 6. Salva manifesto de producao
# ============================================================
manifesto_path = MODELOS / "manifesto_producao.json"
with open(manifesto_path, "w", encoding="utf-8") as f:
    json.dump(manifesto_prod, f, indent=2, ensure_ascii=False)

print(f"[OK] Manifesto: {manifesto_path.name} ({manifesto_path.stat().st_size / 1024:.1f} KB)")
print()
print("=" * 70)
print("  FIM")
print("=" * 70)


