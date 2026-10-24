import pandas as pd
import numpy as np
from pathlib import Path
import json

BASE = Path.cwd()
DATA_DIR = BASE / "data"

FILE_OPENMETEO = DATA_DIR / "previsao_chuva_bacia.csv"
FILE_ECMWF = DATA_DIR / "previsao_chuva_ecmwf.csv"
OUT_JSON = DATA_DIR / "chuva_ensemble_consolidada.json"

print("=== ARCTURUS CLIMATIK: CONFRONTO E ENSEMBLE DE PREVISÃO DE CHUVA ===")

# --- 1. CARREGAMENTO E LEITURA OPEN-METEO ---
total_openmeteo = 0.0
if FILE_OPENMETEO.exists():
    try:
        df_om = pd.read_csv(FILE_OPENMETEO)
        col_chuva = next((c for c in df_om.columns if 'chuva' in c.lower() or 'precip' in c.lower()), None)
        if col_chuva:
            total_openmeteo = float(df_om[col_chuva].iloc[:48].sum())
            print(f"[OK] Open-Meteo carregado: {total_openmeteo:.1f} mm (48h)")
        else:
            print("[AVISO] Coluna de chuva não identificada no arquivo da Open-Meteo.")
    except Exception as e:
        print(f"[ERRO] Falha ao ler Open-Meteo: {e}")
else:
    print("[AVISO] Arquivo previsao_chuva_bacia.csv não localizado.")

# --- 2. CARREGAMENTO E LEITURA ECMWF ---
total_ecmwf = 0.0
if FILE_ECMWF.exists():
    try:
        df_ec = pd.read_csv(FILE_ECMWF)
        col_chuva = next((c for c in df_ec.columns if 'chuva' in c.lower() or 'precip' in c.lower()), None)
        if col_chuva:
            total_ecmwf = float(df_ec[col_chuva].iloc[:48].sum())
            print(f"[OK] ECMWF IFS carregado: {total_ecmwf:.1f} mm (48h)")
        else:
            print("[AVISO] Coluna de chuva não identificada no arquivo do ECMWF.")
    except Exception as e:
        print(f"[ERRO] Falha ao ler ECMWF: {e}")
else:
    print("[AVISO] Arquivo previsao_chuva_ecmwf.csv não localizado.")

# --- 3. CÁLCULO DE ESTATÍSTICAS E ANÁLISE DE INCERTEZA ---
media_chuva = (total_openmeteo + total_ecmwf) / 2.0
pior_caso = max(total_openmeteo, total_ecmwf)
diferenca_abs = abs(total_openmeteo - total_ecmwf)

# Limiar de incerteza crítica: divergência superior a 20 mm
LIMIAR_INCERTEZA = 20.0
incerteza_alta = diferenca_abs > LIMIAR_INCERTEZA

print("\n" + "="*60)
print("📊 RESUMO DO CONFRONTO DE PREVISÃO (48 HORAS)")
print("="*60)
print(f"• Fonte A (Open-Meteo):   {total_openmeteo:6.1f} mm")
print(f"• Fonte B (ECMWF IFS):    {total_ecmwf:6.1f} mm")
print(f"• Média das Fontes:       {media_chuva:6.1f} mm")
print(f"• Pior Caso (Conservador): {pior_caso:6.1f} mm  <-- Valor recomendado para o Alerta")
print(f"• Amplitude de Incerteza: {diferenca_abs:6.1f} mm")

if incerteza_alta:
    print("\n🚨 ALERTA DE ALTA INCERTEZA METEOROLÓGICA!")
    print(f"   A divergência entre os modelos ({diferenca_abs:.1f} mm) ultrapassou o limiar de {LIMIAR_INCERTEZA:.1f} mm.")
    print("   Recomendação: Adotar a premissa do Pior Caso (Conservador) na matriz de decisão do ARCTURUS.")
else:
    print("\n✅ COERÊNCIA MODELAR: Os modelos apresentam convergência dentro da margem aceitável.")

# --- 4. CONSOLIDAÇÃO EM JSON PARA O PAINEL ---
payload = {
    "openmeteo_48h_mm": round(total_openmeteo, 2),
    "ecmwf_48h_mm": round(total_ecmwf, 2),
    "media_48h_mm": round(media_chuva, 2),
    "pior_caso_48h_mm": round(pior_caso, 2),
    "diferenca_mm": round(diferenca_abs, 2),
    "incerteza_alta": bool(incerteza_alta)
}

with open(OUT_JSON, "w", encoding="utf-8") as f:
    json.dump(payload, f, indent=4)

print(f"\n[OK] Resultado consolidado salvo em: {OUT_JSON}")

