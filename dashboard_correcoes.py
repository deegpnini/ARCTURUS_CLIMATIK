import json
import pandas as pd
from pathlib import Path
from datetime import datetime

BASE_DIR = Path.home() / "projetos" / "arcturus_coleta"
PREVISAO_CSV = sorted((BASE_DIR / "dados_previsao").glob("previsao_tempo_real_*.csv"))[-1]
DASHBOARD_JSON = BASE_DIR / "data" / "dashboard_status.json"

def get_chuva_48h():
    """Lê a previsão de chuva para hoje e amanhã (48h)."""
    df = pd.read_csv(PREVISAO_CSV, parse_dates=["date"])
    hoje = datetime.now().strftime("%Y-%m-%d")
    amanha = (datetime.now() + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    chuva_hoje = df[df["date"] == hoje]["chuva_prevista_mm"].values[0] if len(df[df["date"] == hoje]) > 0 else 0.0
    chuva_amanha = df[df["date"] == amanha]["chuva_prevista_mm"].values[0] if len(df[df["date"] == amanha]) > 0 else 0.0
    return chuva_hoje + chuva_amanha

def get_status_unificado():
    """Lê o status unificado do JSON."""
    if DASHBOARD_JSON.exists():
        data = json.loads(DASHBOARD_JSON.read_text())
        return data["status_unificado"], data["cor"], data["score"]
    return "🔴 OFFLINE", "red", 0

def get_selo_confianca():
    """Retorna o selo correto para o v11c."""
    return "🟡 SOMBRA / EXPERIMENTAL", "orange", "MAE ±22 cm"

def get_cota_v11c():
    """Lê a última previsão do v11c no log de sombra."""
    log_file = BASE_DIR / "data" / "log_previsoes_sombra.csv"
    if log_file.exists():
        df = pd.read_csv(log_file)
        ultima = df.iloc[-1]
        return ultima["cota_hoje_cm"], ultima["delta_previsto_cm"], ultima["cota_prevista_amanha_cm"]
    return None, None, None
