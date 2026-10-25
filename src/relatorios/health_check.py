import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from src.relatorios.log_incidentes import registrar
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
AGORA = datetime.now()

def verificar_arquivo(caminho, max_minutos=20):
    if not caminho.exists():
        return {"status": "🔴 OFFLINE", "motivo": "Arquivo não existe"}
    mtime = datetime.fromtimestamp(caminho.stat().st_mtime)
    idade = (AGORA - mtime).total_seconds() / 60
    if idade > max_minutos:
        return {"status": "🔴 ATRASADO", "motivo": f"Sem atualização há {idade:.0f} min"}
    return {"status": "🟢 ONLINE", "idade_min": round(idade, 1)}

status = {
    "timestamp": AGORA.isoformat(),
    "sensor_erab": verificar_arquivo(BASE / "tubarao_saneamento_dados.json", 20),
    "pipeline_regime": verificar_arquivo(BASE / "data" / "regime_atual.json", 20),
    "chuva_ensemble": verificar_arquivo(BASE / "data" / "chuva_ensemble_consolidada.json", 90),
    "simulacao": verificar_arquivo(BASE / "data" / "simulacao_probabilidade_atual.json", 90)
}

with open(BASE / "data" / "health_check.json", "w") as f:
    json.dump(status, f, indent=2)

# --- REGISTRO DE INCIDENTES (IDEIA DO ENGENHEIRO) ---
if status["sensor_erab"].get("idade_min", 0) > 30:
    registrar("SENSOR_OFFLINE", {"idade_min": status["sensor_erab"]["idade_min"]})
if status["pipeline_regime"].get("idade_min", 0) > 20:
    registrar("PIPELINE_ATRASADO", {"idade_min": status["pipeline_regime"]["idade_min"]})

# Verifica a confiança da chuva
try:
    with open(BASE / "data" / "chuva_ensemble_consolidada.json") as f:
        chuva = json.load(f)
        score = chuva.get("confianca_score", 100)
        if score < 25:
            registrar("CHUVA_CONFIANCA_BAIXA", {"confianca_score": score})
except Exception:
    pass

print(f"✅ Health Check salvo. ERAB: {status['sensor_erab']['status']} | Regime: {status['pipeline_regime']['status']}")
