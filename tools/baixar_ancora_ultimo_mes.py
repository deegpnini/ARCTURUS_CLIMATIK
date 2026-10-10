"""Baixa os ultimos 30 dias da ancora (Tubarao 84580000)."""
import json, sys
from pathlib import Path
from datetime import date
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from ana_auth import get_token

API = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"
CODE = "84580000"

token = get_token()
hoje = date.today().strftime("%Y-%m-%d")

query = (
    f"C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o={CODE}"
    f"&Tipo%20Filtro%20Data=DATA_LEITURA"
    f"&Range%20Intervalo%20de%20busca=DIAS_30"
    f"&Data%20de%20Busca%20(yyyy-MM-dd)={hoje}"
)
req = Request(f"{API}?{query}", headers={"Authorization": f"Bearer {token}"})
with urlopen(req, timeout=90) as r:
    data = json.loads(r.read().decode("utf-8"))
    items = data.get("items") or []
    print(f"Recebidos: {len(items)}")
    if items:
        print(f"Periodo: {items[0].get('Data_Hora_Medicao')} -> {items[-1].get('Data_Hora_Medicao')}")
        out = ROOT / "data" / "ancora_ultimo_mes.json"
        with out.open("w", encoding="utf-8") as f:
            json.dump(items, f, ensure_ascii=False, indent=2)
        print(f"[OK] {out.name} ({out.stat().st_size/1024:.0f} KB)")
