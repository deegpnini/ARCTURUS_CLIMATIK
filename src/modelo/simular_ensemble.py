import json
import numpy as np
import pandas as pd
import lightgbm as lgb
from pathlib import Path

BASE = Path.cwd()

# 1. Carregar os 3 modelos v2
modelos = []
for i in range(3):
    caminho = BASE / "modelos" / f"classificador_v2_seed{i}.txt"
    if not caminho.exists():
        raise FileNotFoundError(f"Modelo não encontrado: {caminho}")
    modelos.append(lgb.Booster(model_file=str(caminho)))

# 2. Carregar manifesto v2 (limiares)
with open(BASE / "modelos" / "manifesto_classificador_v2.json") as f:
    manifesto = json.load(f)
limiar = manifesto["limiares_por_orcamento_ano"]["10"]  # orçamento 10/ano
features = manifesto["features"]

# 3. Carregar cota atual
with open(BASE / "tubarao_saneamento_dados.json") as f:
    cota = json.load(f).get("cota_cm", 65.0)

# 4. Carregar Ensemble (chuva prevista)
with open(BASE / "data" / "chuva_ensemble_consolidada.json") as f:
    ens = json.load(f)
chuva_pior = ens.get("pior_caso_48h_mm", 0.0)

# 5. Montar features (sem coluna constante; chuva nas colunas certas)
# Como não temos a chuva observada diária, usamos o Ensemble como proxy para as features de chuva.
# Isso é uma aproximação; o ideal é ler a chuva observada do histórico.
X = pd.DataFrame([{
    "cota": cota,
    "d1": 0.0, "d3": 0.0, "max3": cota,
    "sin": np.sin(2 * np.pi * 297 / 365.25),
    "cos": np.cos(2 * np.pi * 297 / 365.25),
    "chuva_1d": chuva_pior / 2,  # proxy: metade da chuva de 48h em 1 dia
    "chuva_2d": chuva_pior,
    "chuva_3d": chuva_pior * 1.2,
    "chuva_5d": chuva_pior * 1.5,
    "chuva_10d": chuva_pior * 2.0,
    "chuva_30d": chuva_pior * 3.0,
    "chuva_max_ponto_2d": chuva_pior,
}])
X = X[features]

# 6. Média das 3 sementes
probs = [m.predict(X)[0] for m in modelos]
prob_final = float(np.mean(probs))

# 7. Comparar com o limiar
print(f"Cota: {cota:.1f} cm | Chuva Pior Caso: {chuva_pior:.1f} mm")
print(f"Probabilidade média (3 sementes): {prob_final:.4f}")
print(f"Limiar (orçamento 10/ano): {limiar:.4f}")
if prob_final >= limiar:
    print(f"🚨 ALERTA: probabilidade acima do limiar.")
else:
    print(f"✅ Normal: probabilidade abaixo do limiar.")

# 8. Salvar no JSON
with open(BASE / "data" / "simulacao_probabilidade_atual.json", "w") as f:
    json.dump({"prob_media": round(prob_final, 6), "limiar": limiar,
               "alerta": bool(prob_final >= limiar)}, f, indent=2)
