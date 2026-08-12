# ============================================================
# ARCTURUS CLIMATIK — SCRIPT DE EXEMPLO
# ============================================================

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score

print("🚀 ARCTURUS CLIMATIK — SCRIPT DE EXEMPLO")

# Carregar dados
df = pd.read_csv("dados/amostra_dados.csv")
print(f"✅ Dados carregados: {df.shape[0]} registros")
