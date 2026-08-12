
# ============================================================
# ARCTURUS CLIMATIK — PIPELINE COMPLETO
# ============================================================
import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error, r2_score
from sklearn.model_selection import TimeSeriesSplit

print("🚀 ARCTURUS CLIMATIK — PIPELINE")
print("="*60)

# Carregar dados
df = pd.read_csv("dados/dados.csv")
print(f"✅ {len(df)} registros carregados")
