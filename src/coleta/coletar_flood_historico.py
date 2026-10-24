import requests
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
LAT = -28.4206
LON = -49.1064
URL = "https://flood-api.open-meteo.com/v1/flood"

def coletar_historico():
    print("Baixando histórico de vazão do GloFAS (2023-2026)...")
    # CORREÇÃO: Remover 'forecast_days'. A API não aceita junto com start_date/end_date.
    params = {
        "latitude": LAT,
        "longitude": LON,
        "daily": "river_discharge",
        "start_date": "2023-11-25",
        "end_date": "2026-09-21"
    }
    try:
        r = requests.get(URL, params=params, timeout=60)
        if r.status_code == 200:
            dados = r.json()
            df = pd.DataFrame({
                "data": dados.get("daily", {}).get("time", []),
                "vazao_glofas_m3s": dados.get("daily", {}).get("river_discharge", [])
            })
            df["data"] = pd.to_datetime(df["data"])
            df = df.set_index("data")
            caminho = BASE / "data" / "flood_glofas_historico.csv"
            df.to_csv(caminho)
            print(f"✅ Salvo em: {caminho} ({len(df)} linhas)")
            print(f"   Vazão mínima: {df['vazao_glofas_m3s'].min():.1f} m³/s")
            print(f"   Vazão máxima: {df['vazao_glofas_m3s'].max():.1f} m³/s")
        else:
            print(f"❌ Erro HTTP: {r.status_code}")
            print(f"   Resposta da API: {r.text[:500]}")
    except Exception as e:
        print(f"❌ Erro: {e}")

if __name__ == "__main__":
    coletar_historico()
