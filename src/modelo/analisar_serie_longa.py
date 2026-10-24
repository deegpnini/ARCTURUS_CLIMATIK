import pandas as pd
import numpy as np
from pathlib import Path
import json

BASE = Path(__file__).resolve().parents[2]

# 1. Carregar a série longa (nome real do arquivo)
caminho = BASE / "data" / "ana_longa84580000.csv"
print(f"Carregando: {caminho}")

if not caminho.exists():
    print("❌ Arquivo não encontrado.")
    exit()

df = pd.read_csv(caminho)
print(f"Colunas: {df.columns.tolist()}")
print(f"Total de linhas: {len(df)}")
print(df.head())

# Identificar a coluna de cota
col_cota = [c for c in df.columns if 'cota' in c.lower()]
if not col_cota:
    print("❌ Coluna de cota não encontrada.")
    exit()
col_cota = col_cota[0]
print(f"\nColuna de cota: {col_cota}")

# Limpar e converter
df[col_cota] = pd.to_numeric(df[col_cota], errors='coerce')
df = df.dropna(subset=[col_cota])
print(f"Linhas com cota válida: {len(df)}")
print(f"Cota máxima: {df[col_cota].max():.0f} cm")
print(f"Cota mínima: {df[col_cota].min():.0f} cm")

# Contar eventos extremos (cota > 300 cm)
eventos_extremos = df[df[col_cota] > 300]
print(f"\nTotal de dias com cota > 300 cm: {len(eventos_extremos)}")

# Identificar a coluna de data
col_data = [c for c in df.columns if 'data' in c.lower()]
if col_data:
    col_data = col_data[0]
    print(f"Coluna de data: {col_data}")
    
    if len(eventos_extremos) > 0:
        eventos_extremos = eventos_extremos.copy()
        eventos_extremos[col_data] = pd.to_datetime(eventos_extremos[col_data], errors='coerce')
        eventos_extremos = eventos_extremos.dropna(subset=[col_data])
        eventos_extremos = eventos_extremos.sort_values(col_data)
        
        # Agrupar eventos separados por mais de 7 dias
        eventos_extremos['grupo'] = (eventos_extremos[col_data].diff() > pd.Timedelta(days=7)).cumsum()
        
        print(f"\nEventos extremos (cota > 300 cm):")
        for grupo, dados in eventos_extremos.groupby('grupo'):
            inicio = dados[col_data].min()
            fim = dados[col_data].max()
            max_cota = dados[col_cota].max()
            print(f"  Evento {grupo}: {inicio.date()} a {fim.date()} | Cota máxima: {max_cota:.0f} cm")

# 2. Salvar um resumo
resumo = {
    "total_linhas": len(df),
    "cota_max": float(df[col_cota].max()),
    "cota_min": float(df[col_cota].min()),
    "eventos_extremos": len(eventos_extremos) if len(eventos_extremos) > 0 else 0
}
with open(BASE / "data" / "serie_longa_resumo.json", "w") as f:
    json.dump(resumo, f, indent=2)
print(f"\n✅ Resumo salvo em: data/serie_longa_resumo.json")
