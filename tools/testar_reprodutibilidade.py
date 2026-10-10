"""
Testa que cada modelo salvo reproduz previsao identica a assinatura no manifesto.
Se passar, o modelo e' confiavel pra producao.
"""
import os
import json
import hashlib
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)

DATA = ROOT / "data"
MODELOS = ROOT / "modelos"

def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()

# Carrega manifesto
with open(MODELOS / "manifesto_producao.json", encoding="utf-8") as f:
    manifest = json.load(f)

print("=" * 70)
print("  TESTE DE REPRODUTIBILIDADE")
print("=" * 70)
print()

todos_ok = True

for h, info in manifest["horizontes"].items():
    print(f"--- Horizonte {h} ---")

    # 1. Verifica hash do modelo
    model_path = MODELOS / info["arquivo"]
    hash_atual = sha256(model_path)
    hash_esperado = info["sha256_modelo"]

    if hash_atual == hash_esperado:
        print(f"  [OK] sha256 bate: {hash_atual[:16]}...")
    else:
        print(f"  [FALHA] sha256 diferente:")
        print(f"         esperado: {hash_esperado[:16]}...")
        print(f"         atual:    {hash_atual[:16]}...")
        todos_ok = False
        continue

    # 2. Verifica reprodutibilidade da previsao
    # Carrega dataset
    df = pd.read_csv(DATA / f"dataset_{h}.csv")
    target_abs = f"target_{h}"
    feats = [c for c in df.columns if c not in ("timestamp", target_abs, "vazao")]
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df["target_delta"] = df[target_abs] - df["cota"]

    # Filtra linhas com target valido (mesma regra do treino)
    df_train = df[df["target_delta"].notna()].copy()
    X = df_train[feats].values

    # Carrega modelo
    model = lgb.Booster(model_file=str(model_path))

    # Preve a ultima linha
    pred = float(model.predict(X[-1:])[0])
    esperado = info["assinatura_reprodutibilidade"]["valor_esperado"]

    if np.isclose(pred, esperado, atol=1e-6):
        print(f"  [OK] assinatura bate: {pred:.6f}")
    else:
        print(f"  [FALHA] assinatura diferente:")
        print(f"         esperado: {esperado:.6f}")
        print(f"         atual:    {pred:.6f}")
        todos_ok = False

    # 3. Verifica numero de features
    n_feats_modelo = model.num_feature()
    n_feats_manifest = info["n_features"]
    if n_feats_modelo == n_feats_manifest:
        print(f"  [OK] n_features bate: {n_feats_modelo}")
    else:
        print(f"  [FALHA] n_features diferente: modelo={n_feats_modelo} manifesto={n_feats_manifest}")
        todos_ok = False

    print()

print("=" * 70)
if todos_ok:
    print("  VEREDITO: MODELOS CONFIAVEIS PARA PRODUCAO")
else:
    print("  VEREDITO: FALHA — NAO USAR EM PRODUCAO")
print("=" * 70)
