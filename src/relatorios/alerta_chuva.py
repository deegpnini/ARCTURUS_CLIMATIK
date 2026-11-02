import requests
import pandas as pd
from datetime import datetime, timedelta

# Coordenadas de São Ludgero
LAT = -28.3
LON = -49.1

def verificar_chuva():
    hoje = datetime.now().strftime("%Y%m%d")
    ontem = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    
    url = f"https://power.larc.nasa.gov/api/temporal/daily/point?parameters=PRECTOTCORR&community=AG&longitude={LON}&latitude={LAT}&start={ontem}&end={hoje}&format=JSON"
    r = requests.get(url)
    
    if r.status_code == 200:
        dados = r.json()["properties"]["parameter"]["PRECTOTCORR"]
        for data, chuva in dados.items():
            if chuva != -999.0:
                print(f"{data}: {chuva:.1f} mm de chuva")
                if chuva > 50:
                    print(f"🚨 ALERTA: Chuva forte detectada em {data} ({chuva:.1f} mm)")
    else:
        print(f"Erro NASA: {r.status_code}")

if __name__ == "__main__":
    verificar_chuva()
