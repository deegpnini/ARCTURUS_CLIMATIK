# ============================================================
# ARCTURUS CLIMATIK — PIPELINE COMPLETO
# ============================================================
# Este script:
# 1. Carrega EPAGRI e INMET
# 2. Padroniza e consolida
# 3. Aplica correções de vieses
# 4. Gera dataset final
# ============================================================

import pandas as pd
import numpy as np
import os
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')

print("🚀 ARCTURUS CLIMATIK — PIPELINE COMPLETO")
print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
print("="*60)

# ============================================================
# CONFIGURAÇÕES
# ============================================================
ESTACOES_VALIDAS = [
    '1027', '1047', '1061', '1070', '2130', '2242', '2244', '2255',
    '2301', '2355', '2363', '2369', '2377', '2383', '2414', '2424',
    '2441', '2462', '2469', '2927', '2975'
]

OVERLAP_PAIRS = [
    ("2441", "A867"),
    ("2424", "A895"),
    ("1027", "A814"),
    ("2927", "A868"),
]

EXCLUDED = ["2414", "A865"]

# ============================================================
# CARREGAR DADOS
# ============================================================
print("\n📂 CARREGANDO DADOS...")

df_epagri = pd.read_csv("/content/drive/MyDrive/CLIMATIK/epagri_MASTER.csv", low_memory=False)
print(f"  ✅ EPAGRI: {df_epagri.shape[0]:,} registros, {df_epagri['estacao_codigo'].nunique()} estações")

df_inmet = pd.read_csv("/content/drive/MyDrive/ARCTURUS_CLIMATIK/inmet_sc_completo_2024_2026.csv", low_memory=False)
print(f"  ✅ INMET: {df_inmet.shape[0]:,} registros, {df_inmet['id_estacao'].nunique()} estações")

# ============================================================
# PADRONIZAR
# ============================================================
print("\n🔄 PADRONIZANDO...")

# EPAGRI
df_epagri_clean = df_epagri[['estacao_codigo', 'Data Horario', 'TempArInst(C)', 'UmidRelMedia(%)', 'Precipitacao(mm)']].copy()
df_epagri_clean.columns = ['id_estacao', 'data_hora', 'temperatura', 'umidade', 'precipitacao']
df_epagri_clean['fonte'] = 'EPAGRI'
df_epagri_clean['data_hora'] = pd.to_datetime(df_epagri_clean['data_hora'], format='%d/%m/%Y %H:%M:%S', errors='coerce')
df_epagri_clean = df_epagri_clean.dropna(subset=['data_hora'])

# INMET
df_inmet_clean = df_inmet[['id_estacao', 'data', 'hora', 'temperatura_inst', 'umidade_rel', 'precipitacao']].copy()
df_inmet_clean['data_hora'] = pd.to_datetime(df_inmet_clean['data'] + ' ' + df_inmet_clean['hora'])
df_inmet_clean.columns = ['id_estacao', 'data', 'hora', 'temperatura', 'umidade', 'precipitacao', 'data_hora']
df_inmet_clean['fonte'] = 'INMET'
df_inmet_clean = df_inmet_clean.dropna(subset=['data_hora'])

# ============================================================
# CONSOLIDAR
# ============================================================
print("\n📊 CONSOLIDANDO...")

df_consolidado = pd.concat([df_epagri_clean, df_inmet_clean], ignore_index=True)
print(f"  ✅ Consolidado: {df_consolidado.shape[0]:,} registros, {df_consolidado['id_estacao'].nunique()} estações")

# ============================================================
# FUSÃO DE SOBREPOSIÇÕES
# ============================================================
print("\n🔗 FUNDINDO SOBREPOSIÇÕES...")

overlap_map = {}
for epagri_id, inmet_id in OVERLAP_PAIRS:
    overlap_map[epagri_id] = f"{epagri_id}+{inmet_id}"
    overlap_map[inmet_id] = f"{epagri_id}+{inmet_id}"

df_consolidado['id_estacao_final'] = df_consolidado['id_estacao'].map(overlap_map).fillna(df_consolidado['id_estacao'])
df_consolidado = df_consolidado[~df_consolidado['id_estacao'].isin(EXCLUDED)]

print(f"  ✅ Estações finais: {df_consolidado['id_estacao_final'].nunique()}")

# ============================================================
# SALVAR
# ============================================================
df_consolidado.to_csv('/content/arcturus_climatik_final_limpo.csv', index=False)
print("\n✅ Dataset final salvo: arcturus_climatik_final_limpo.csv")

print("\n" + "="*60)
print("✅ PIPELINE CONCLUÍDO")
print("="*60)
