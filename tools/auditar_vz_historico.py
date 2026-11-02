import pandas as pd
import numpy as np
import json
import glob
from pathlib import Path

# --- 1. LOCALIZAÇÃO E CARREGAMENTO DOS DADOS ---
BASE = Path.cwd()
print("=== ARCTURUS CLIMATIK: AUDITORIA DE DERIVADA HISTÓRICA (Vz) ===")

# Busca flexível pelos arquivos de cache ou datasets na pasta data/
arquivos_json = glob.glob(str(BASE / "data" / "**" / "*84580000*.json"), recursive=True)
arquivo_csv = BASE / "data" / "dataset_1h_com_montante.csv"

df = pd.DataFrame()

# Tenta carregar os JSONs de telemetria primeiro (prioridade para dados de 15 min)
registros = []
for arq in arquivos_json:
    try:
        with open(arq, 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Adaptação para a estrutura da ANA (lista direta ou dentro de "items")
            items = data.get("items", data) if isinstance(data, dict) else data
            if isinstance(items, list):
                for item in items:
                    if isinstance(item, dict):
                        dt = item.get("Data_Hora_Medicao") or item.get("data")
                        cota = item.get("Cota_Adotada") if "Cota_Adotada" in item else item.get("cota")
                        if dt and cota is not None:
                            registros.append({"data_hora": dt, "cota": cota})
    except Exception as e:
        pass

if registros:
    print(f"[OK] Dados extraídos de {len(arquivos_json)} arquivo(s) JSON (Telemetria).")
    df = pd.DataFrame(registros)
    df['data_hora'] = pd.to_datetime(df['data_hora'], errors='coerce')
    df['cota'] = pd.to_numeric(df['cota'], errors='coerce')

# Se não achou JSON ou falhou, tenta o CSV validado do ARCTURUS
elif arquivo_csv.exists():
    print(f"[OK] JSON não localizado/vazio. Carregando dataset consolidado: {arquivo_csv.name}")
    df = pd.read_csv(arquivo_csv)
    # Busca dinâmica pelas colunas de data e cota
    col_dt = next((c for c in df.columns if 'data' in c.lower() or 'time' in c.lower()), None)
    col_cota = next((c for c in df.columns if 'cota' in c.lower()), None)
    
    if col_dt and col_cota:
        df = df.rename(columns={col_dt: 'data_hora', col_cota: 'cota'})
        df['data_hora'] = pd.to_datetime(df['data_hora'], errors='coerce')
        df['cota'] = pd.to_numeric(df['cota'], errors='coerce')
    else:
        print("[ERRO] Colunas de data/cota não identificadas no CSV.")
        exit(1)
else:
    print("[ERRO] Nenhum arquivo histórico (JSON ou CSV) localizado na pasta data/.")
    exit(1)

# --- 2. CÁLCULO DA DERIVADA (Vz) ---
# Limpeza e ordenação temporal rigorosa
df = df.dropna(subset=['data_hora', 'cota']).drop_duplicates(subset=['data_hora']).sort_values('data_hora')

# Cálculos de delta
df['delta_t_h'] = df['data_hora'].diff().dt.total_seconds() / 3600.0
df['delta_cota'] = df['cota'].diff()

# Filtrar saltos irreais (ex: sensor caiu e voltou 3 dias depois. Isso não é uma derivada válida).
# Aceitamos gaps de no máximo 3 horas para calcular a velocidade contínua.
mask_valida = (df['delta_t_h'] > 0) & (df['delta_t_h'] <= 3.0)
df.loc[mask_valida, 'Vz_cm_h'] = df['delta_cota'] / df['delta_t_h']

# --- 3. ANÁLISE ESTATÍSTICA ---
df_vz = df.dropna(subset=['Vz_cm_h']).copy()
vz_subidas = df_vz[df_vz['Vz_cm_h'] > 0]['Vz_cm_h']

print("\n📊 DISTRIBUIÇÃO DA DERIVADA (Vz - Apenas momentos de subida do rio)")
print("-" * 60)
print(f"Total de medições contínuas válidas: {len(df_vz)}")
print(f"Média das subidas:   {vz_subidas.mean():.2f} cm/h")
print(f"Mediana das subidas: {vz_subidas.median():.2f} cm/h")
print(f"Percentil 95 (P95):  {vz_subidas.quantile(0.95):.2f} cm/h  <-- Acima disso é evento raro")
print(f"Percentil 99 (P99):  {vz_subidas.quantile(0.99):.2f} cm/h  <-- Acima disso é evento extremo")
print(f"Máximo absoluto:     {vz_subidas.max():.2f} cm/h")
print("-" * 60)

# --- 4. RASTREIO DE SUBIDAS ANORMAIS (> 20 cm/h) ---
LIMIAR_CRITICO = 20.0
anormais = df_vz[df_vz['Vz_cm_h'] > LIMIAR_CRITICO].sort_values('Vz_cm_h', ascending=False)

print(f"\n🚨 EVENTOS CRÍTICOS: SUBIDAS > {LIMIAR_CRITICO} cm/h")
if anormais.empty:
    print(f"Nenhum evento registrado acima de {LIMIAR_CRITICO} cm/h na base analisada.")
else:
    print(f"Gatilhos acionados: {len(anormais)} registros históricos.")
    print("\nTop 15 picos de velocidade (Vz):")
    cols_display = ['data_hora', 'cota', 'delta_cota', 'delta_t_h', 'Vz_cm_h']
    print(anormais[cols_display].head(15).to_string(index=False, float_format="%.2f"))

