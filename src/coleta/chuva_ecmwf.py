import os
import pandas as pd
import xarray as xr
from ecmwf.opendata import Client
from pathlib import Path
import warnings

# Suprime warnings sujos da biblioteca do ECMWF
warnings.filterwarnings("ignore")

BASE = Path.cwd()
DATA_DIR = BASE / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)
GRIB_FILE = DATA_DIR / "ecmwf_tp.grib"
CSV_FILE = DATA_DIR / "previsao_chuva_ecmwf.csv"

print("=== NEXUS OIKOS: EXTRAÇÃO BRUTA ECMWF (MODELO IFS) ===")
print("Conectando aos servidores Open Data (Reading, UK)...")

# 1. Download do GRIB2
client = Client(source="ecmwf")

# Passos de 3 em 3 horas até 48h
passos = [3, 6, 9, 12, 15, 18, 21, 24, 27, 30, 33, 36, 39, 42, 45, 48]

try:
    client.retrieve(
        type="fc",
        param="tp",      # Total Precipitation
        step=passos,
        target=str(GRIB_FILE)
    )
    print(f"[OK] Grade binária GRIB2 isolada e baixada: {GRIB_FILE.name}")
except Exception as e:
    print(f"[ERRO CRÍTICO] Falha ao baixar dados do ECMWF: {e}")
    exit(1)

# 2. Decodificação Espacial e Matemática
print("Decodificando tensores e extraindo as coordenadas da bacia...")
try:
    # Abre o binário
    ds = xr.open_dataset(GRIB_FILE, engine="cfgrib")
    
    # Coordenadas do exutório (Bacia do Tubarão)
    LAT_ALVO = -28.3
    LON_ALVO = -49.1
    
    # Correção Física de Longitude (ECMWF costuma usar 0 a 360)
    # Se -49.1 falhar, procuramos 310.9 (360 - 49.1)
    try:
        ponto = ds.sel(latitude=LAT_ALVO, longitude=LON_ALVO, method="nearest")
    except KeyError:
        ponto = ds.sel(latitude=LAT_ALVO, longitude=(360.0 + LON_ALVO), method="nearest")

    # Extrai para DataFrame
    df = ponto.to_dataframe().reset_index()

    # Identificação dinâmica das colunas de tempo e chuva
    col_tempo = 'valid_time' if 'valid_time' in df.columns else 'time'
    
    df = df[[col_tempo, 'step', 'tp']].rename(columns={col_tempo: 'data_hora'})
    
    # MATEMÁTICA DA CHUVA:
    # 1. ECMWF envia o dado em METROS. Multiplicamos por 1000 para Milímetros.
    df['chuva_acumulada_mm'] = df['tp'] * 1000.0
    
    # 2. O dado é acumulado desde a hora 0. 
    # A chuva do intervalo de 3h é a derivada discreta da curva acumulada (diff).
    df['chuva_prevista_mm'] = df['chuva_acumulada_mm'].diff().fillna(df['chuva_acumulada_mm'])
    
    # Limpa valores negativos espúrios por erro de arredondamento de float
    df['chuva_prevista_mm'] = df['chuva_prevista_mm'].clip(lower=0)

    # Prepara CSV final para o Classificador ARCTURUS
    df_final = df[['data_hora', 'chuva_prevista_mm']].copy()
    df_final['data_hora'] = pd.to_datetime(df_final['data_hora'])
    df_final.set_index('data_hora', inplace=True)

    # Salva no disco
    df_final.to_csv(CSV_FILE)
    
    total_48h = df_final['chuva_prevista_mm'].sum()

    print("-" * 60)
    print("✅ Gêmeo Digital Alimentado com Sucesso (Fonte de Grau Militar)!")
    print(f"📍 Coordenada Lida: Lat {ponto.latitude.values:.2f} | Lon {ponto.longitude.values:.2f}")
    print(f"🌧️ Chuva Total Prevista (48h): {total_48h:.1f} mm")
    print(f"📁 Arquivo salvo em: {CSV_FILE}")
    print("-" * 60)

except Exception as e:
    print(f"[ERRO] Falha no processamento numérico do GRIB2: {e}")
    print("Execute 'sudo apt-get install libeccodes0' no bash caso não tenha feito.")
