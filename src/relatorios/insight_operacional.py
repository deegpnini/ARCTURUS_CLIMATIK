import json
import pandas as pd
import numpy as np
import lightgbm as lgb
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).resolve().parents[2]
MODELOS = BASE / "modelos"

def checar_frescor(extraido_iso, limite_min=45):
    idade = datetime.now() - datetime.fromisoformat(extraido_iso)
    if idade > timedelta(minutes=limite_min):
        return False, idade
    return True, idade

def main():
    print("=== ARCTURUS v8: MODO OPERACIONAL ===")
    caminho_json = BASE / "tubarao_saneamento_dados.json"
    if not caminho_json.exists():
        print("❌ JSON não encontrado. Rode coletar_tubarao_saneamento.py primeiro.")
        return
    
    with open(caminho_json, "r") as f:
        dados = json.load(f)
    
    cota = dados.get("cota_cm", 65.0)
    extraido = dados.get("data_extracao", "2000-01-01T00:00:00")
    
    fresco, idade = checar_frescor(extraido)
    if not fresco:
        print(f"🚨 DADO VELHO! Extraído em {extraido} ({idade}).")
        print("   PREVISÃO SUSPENSA. O painel não deve exibir como atual.")
        return
    
    print(f"✅ Dado fresco: {extraido} (idade: {idade})")
    print(f"Cota atual: {cota:.1f} cm")
    
    # Carregar o modelo v8
    for h in ["1h", "3h", "6h"]:
        caminho = MODELOS / f"modelo_delta_{h}_v8_final.txt"
        if not caminho.exists():
            print(f"⚠️ Modelo {h} não encontrado.")
            continue
        m = lgb.Booster(model_file=str(caminho))
        feats = m.feature_name()
        X_dict = {f: 0.0 for f in feats}
        X_dict["cota"] = cota
        X = np.array([[X_dict[f] for f in feats]])
        pred = m.predict(X)[0]
        pred = max(min(pred, 150.0), -150.0)
        print(f"  +{h}: {cota + pred:.1f} cm (delta {pred:+.1f} cm)")

if __name__ == "__main__":
    main()
