#!/usr/bin/env python3
import lightgbm as lgb
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
MODELOS = {
    "1h": BASE / "modelos" / "modelo_delta_1h_v8_final.txt",
    "3h": BASE / "modelos" / "modelo_delta_3h_v8_final.txt",
    "6h": BASE / "modelos" / "modelo_delta_6h_v8_final.txt",
}

for h, path in MODELOS.items():
    if not path.exists():
        print(f"[AVISO] Modelo {h} não encontrado: {path}")
        continue
    modelo = lgb.Booster(model_file=str(path))
    importancias = modelo.feature_importance(importance_type="gain")
    nomes = modelo.feature_name()
    df = pd.DataFrame({"feature": nomes, "importance": importancias}).sort_values("importance", ascending=False)
    print(f"\n=== Feature Importance ({h}) ===")
    print(df.head(10).to_string(index=False))
