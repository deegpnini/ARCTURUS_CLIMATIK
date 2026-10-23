import pandas as pd
import numpy as np
import json
import os
from pathlib import Path

# Caminhos
BASE_DIR = Path(__file__).resolve().parents[2]
CACHE = BASE_DIR / "cache"

def processar_estacao(codigo, nome_curto):
    caminho = CACHE / f"ana_5anos_{codigo}.json"
    if not caminho.exists():
        print(f"⚠️ Arquivo {caminho} não encontrado.")
        return None
    
    print(f"Processando {codigo} ({nome_curto})...")
    with open(caminho, "r") as f:
        dados = json.load(f)
    
    df = pd.DataFrame(dados)
    df['Data_Hora_Medicao'] = pd.to_datetime(df['Data_Hora_Medicao'])
    df = df.sort_values('Data_Hora_Medicao')
    
    # Transformar Cota em Delta (variação)
    df['cota_num'] = pd.to_numeric(df['Cota_Adotada'], errors='coerce')
    df = df.set_index('Data_Hora_Medicao')
    
    # Reamostrar para 1 hora (pegando a última leitura da hora)
    df_hora = df['cota_num'].resample('1h').last()
    
    # Delta = valor atual - valor de 1h atrás
    delta_hora = df_hora.diff()
    
    df_final = pd.DataFrame({
        f'{nome_curto}_cota_abs': df_hora,
        f'{nome_curto}_delta_1h': delta_hora
    })
    
    print(f"  -> {len(df_final)} horas processadas.")
    return df_final

def main():
    print("=== INJEÇÃO DE MONTANTE (OPÇÃO A: DELTA) ===")
    
    estacoes = [
        ("84538500", "sao_mauricio"),
        ("84535000", "rio_fortuna"),
        ("70110000", "invernadinha")
    ]
    
    dfs = []
    for cod, nome in estacoes:
        df = processar_estacao(cod, nome)
        if df is not None:
            dfs.append(df)
            
    if not dfs:
        print("❌ Nenhum dado processado. Abortando.")
        return

    df_montante = pd.concat(dfs, axis=1)
    
    caminho_dataset = BASE_DIR / "data" / "dataset_1h.csv"
    if not caminho_dataset.exists():
        print(f"⚠️ Dataset principal {caminho_dataset} não encontrado.")
        return
        
    print("Carregando dataset principal...")
    df_principal = pd.read_csv(caminho_dataset)
    
    # Verifica qual é a coluna de tempo
    coluna_tempo = 'Data_Hora_Medicao' if 'Data_Hora_Medicao' in df_principal.columns else 'timestamp'
    df_principal[coluna_tempo] = pd.to_datetime(df_principal[coluna_tempo])
    df_principal = df_principal.set_index(coluna_tempo).sort_index()
    
    print("Alinhando dados de montante com o dataset principal...")
    df_merge = df_principal.join(df_montante, how='left')
    df_merge = df_merge.ffill()
    
    caminho_saida = BASE_DIR / "data" / "dataset_1h_com_montante.csv"
    df_merge.to_csv(caminho_saida)
    
    print(f"\n✅ SUCESSO! Dataset enriquecido salvo em: {caminho_saida}")
    print(f"   Linhas originais: {len(df_principal)}")
    
    # Amostra
    print("\nAmostra dos novos dados (últimas 5 linhas):")
    colunas_novas = [c for c in df_merge.columns if 'delta_1h' in c]
    print(df_merge[colunas_novas].tail())

if __name__ == "__main__":
    main()
