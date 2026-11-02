import pandas as pd
from pathlib import Path

BASE = Path("/home/oikos/projetos/ARCTURUS_CLIMATIK")
HISTORICO = BASE / "resultados" / "historico_previsoes.csv"

# 1. Carregar o dataset de 1h
dataset = pd.read_csv(BASE / "data" / "dataset_1h_com_montante.csv", index_col=0, parse_dates=True)

# 2. Pegar as últimas 10 leituras
ultimas = dataset.tail(10).copy()
ultimas = ultimas.reset_index()

# 3. Montar o CSV
linhas = []
for i, row in ultimas.iterrows():
    linhas.append({
        "timestamp_execucao": row["timestamp"].isoformat(),
        "cota_atual_cm": row["cota"],
        "cota_1h_cm": None,
        "delta_1h_cm": None,
        "cota_3h_cm": None,
        "delta_3h_cm": None,
        "cota_6h_cm": None,
        "delta_6h_cm": None,
    })

df_hist = pd.DataFrame(linhas)
df_hist.to_csv(HISTORICO, index=False)
print(f"✅ Histórico de teste criado com {len(df_hist)} leituras.")
print(df_hist.tail(3).to_string())
