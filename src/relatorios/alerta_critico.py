import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
HISTORICO = BASE / "resultados" / "historico_previsoes.csv"

# Limiares de segurança (em cm/hora)
LIMIAR_1H = 30.0   # Subida de 30 cm em 1h = atenção
LIMIAR_3H = 50.0   # Subida de 50 cm em 3h = alerta
LIMIAR_6H = 80.0   # Subida de 80 cm em 6h = perigo

def verificar():
    if not HISTORICO.exists():
        print("⚠️ Histórico não encontrado. O monitor contínuo já rodou?")
        return
    
    df = pd.read_csv(HISTORICO)
    if df.empty:
        print("⚠️ Histórico vazio.")
        return
    
    ultima = df.iloc[-1]
    print(f"\n=== VERIFICAÇÃO DE ALERTA ===")
    print(f"Última previsão: {ultima['timestamp_execucao']}")
    print(f"Cota atual: {ultima['cota_atual_cm']:.1f} cm")
    
    alertas = []
    
    if pd.notna(ultima.get('delta_1h_cm')) and ultima['delta_1h_cm'] > LIMIAR_1H:
        alertas.append(f"🔴 1h: delta {ultima['delta_1h_cm']:+.1f} cm/h (limiar: {LIMIAR_1H})")
    
    if pd.notna(ultima.get('delta_3h_cm')) and ultima['delta_3h_cm'] > LIMIAR_3H:
        alertas.append(f"🔴 3h: delta {ultima['delta_3h_cm']:+.1f} cm (limiar: {LIMIAR_3H})")
    
    if pd.notna(ultima.get('delta_6h_cm')) and ultima['delta_6h_cm'] > LIMIAR_6H:
        alertas.append(f"🔴 6h: delta {ultima['delta_6h_cm']:+.1f} cm (limiar: {LIMIAR_6H})")
    
    if alertas:
        print("\n🚨 ALERTA CRÍTICO DISPARADO:")
        for a in alertas:
            print(f"   {a}")
    else:
        print("\n✅ Nenhum limiar de alerta atingido.")

if __name__ == "__main__":
    verificar()
