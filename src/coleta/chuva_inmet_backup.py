import requests
import pandas as pd
from pathlib import Path
from datetime import datetime, timedelta

BASE = Path(__file__).resolve().parents[2]
URL_INMET = "https://apitempo.inmet.gov.br/estacao/dados"

def buscar_chuva_inmet():
    estacoes = ["A806", "A807", "A808"]
    hoje = datetime.now().strftime("%Y-%m-%d")
    
    for cod in estacoes:
        try:
            url = f"{URL_INMET}/{hoje}/{hoje}/{cod}"
            r = requests.get(url, timeout=30)
            if r.status_code == 200:
                dados = r.json()
                if dados:
                    df = pd.DataFrame(dados)
                    if "CHUVA" in df.columns:
                        total = pd.to_numeric(df["CHUVA"], errors="coerce").sum()
                        print(f"✅ Estação {cod}: {total:.1f} mm de chuva hoje.")
                        return total
        except Exception as e:
            print(f"⚠️ Erro na estação {cod}: {e}")
    return 0.0

if __name__ == "__main__":
    print("=== BACKUP INMET (Chuva Hoje) ===")
    total = buscar_chuva_inmet()
    print(f"Total: {total:.1f} mm")
