import pandas as pd
from pathlib import Path
import json
from datetime import datetime

BASE = Path(__file__).resolve().parents[2]
HISTORICO = BASE / "resultados" / "historico_previsoes.csv"
REGIME_FILE = BASE / "data" / "regime_atual.json"
ENSEMBLE_FILE = BASE / "data" / "chuva_ensemble_consolidada.json"

# Limiares calibrados
LIMIAR_ATENCAO = 20.0   # P95
LIMIAR_EXTREMO = 52.0   # P99
LIMIAR_CHEIA_RELAMPAGO = 100.0

def calcular_derivada():
    if not HISTORICO.exists():
        print("❌ Histórico não encontrado.")
        return
    
    df = pd.read_csv(HISTORICO)
    if len(df) < 2:
        print("⚠️ Histórico tem menos de 2 leituras.")
        return
    
    ultima = df.iloc[-1]
    penultima = df.iloc[-2]
    
    cota_atual = ultima.get("cota_atual_cm", 0)
    cota_anterior = penultima.get("cota_atual_cm", 0)
    
    t_atual = pd.to_datetime(ultima.get("timestamp_execucao", datetime.now()))
    t_anterior = pd.to_datetime(penultima.get("timestamp_execucao", datetime.now()))
    delta_t_horas = (t_atual - t_anterior).total_seconds() / 3600
    
    if delta_t_horas <= 0:
        return
    
    vz = (cota_atual - cota_anterior) / delta_t_horas
    
    # Ler a incerteza do ensemble (se existir)
    incerteza_alta = False
    if ENSEMBLE_FILE.exists():
        with open(ENSEMBLE_FILE, "r") as f:
            ens = json.load(f)
        incerteza_alta = ens.get("incerteza_alta", False)
    
    # Ajuste do limiar de atenção (se incerteza alta, baixa de 20 para 12)
    limiar_atencao = 12.0 if incerteza_alta else LIMIAR_ATENCAO
    
    print(f"=== MONITOR DE DERIVADA (Vz) ===")
    print(f"Cota atual: {cota_atual:.1f} cm")
    print(f"Vz: {vz:+.1f} cm/h")
    print(f"Incerteza alta: {incerteza_alta}")
    print(f"Limiar de atenção: {limiar_atencao} cm/h")
    
    if vz > LIMIAR_CHEIA_RELAMPAGO:
        regime = "EXTREMO"
        motivo = f"Vz = {vz:+.1f} cm/h (cheia relâmpago)"
    elif vz > LIMIAR_EXTREMO:
        regime = "EXTREMO"
        motivo = f"Vz = {vz:+.1f} cm/h (evento extremo)"
    elif vz > limiar_atencao:
        regime = "ATENCAO"
        motivo = f"Vz = {vz:+.1f} cm/h (subida anormal)"
    else:
        regime = "NORMAL"
        motivo = f"Vz = {vz:+.1f} cm/h"
    
    with open(REGIME_FILE, "w") as f:
        json.dump({
            "regime": regime,
            "delta_60m": vz,
            "motivo": motivo,
            "atualizado": datetime.now().isoformat()
        }, f, indent=2)
    print(f"✅ Regime salvo em: {REGIME_FILE}")

if __name__ == "__main__":
    calcular_derivada()
