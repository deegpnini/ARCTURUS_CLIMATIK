# ============================================================
# ARCTURUS CLIMATIK — PIPELINE SIMPLIFICADO
# ============================================================

import pandas as pd
print("🚀 ARCTURUS CLIMATIK — PIPELINE")
print("="*60)

# Carregar dados (exemplo)
df = pd.read_csv("dados/amostra_dados.csv") if os.path.exists("dados/amostra_dados.csv") else pd.DataFrame()
print(f"✅ {len(df)} registros carregados")