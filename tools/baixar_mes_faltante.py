"""
Baixa os ultimos 30 dias (mes faltante dos historicos).
Corrige o bug do parent.parent.
Salva em data/historico_montante_faltante/.
"""
import json, sys, time
from pathlib import Path
from datetime import date
from urllib.request import Request, urlopen

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
from ana_auth import get_token

API_URL = (
    "https://www.ana.gov.br/hidrowebservice/"
    "EstacoesTelemetricas/"
    "HidroinfoanaSerieTelemetricaAdotada/v1"
)

STATIONS = {
    "84249998": "ORLEANS_MONTANTE",
    "84538500": "SAO_MAURICIO_JUSANTE",
    "84536000": "RIO_FORTUNA_JUSANTE",
}

OUTPUT_DIR = PROJECT_ROOT / "data" / "historico_montante_faltante"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def buscar(code, anchor_date, token):
    """Busca 30 dias ate anchor_date (yyyy-MM-dd)."""
    query = (
        f"C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o={code}"
        f"&Tipo%20Filtro%20Data=DATA_LEITURA"
        f"&Range%20Intervalo%20de%20busca=DIAS_30"
        f"&Data%20de%20Busca%20(yyyy-MM-dd)={anchor_date}"
    )
    url = f"{API_URL}?{query}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    with urlopen(req, timeout=90) as resp:
        return json.loads(resp.read().decode("utf-8")).get("items") or []

if __name__ == "__main__":
    token = get_token()
    hoje = date.today().strftime("%Y-%m-%d")

    print("=" * 70)
    print(f"  Baixando mes faltante (anchor={hoje})")
    print("=" * 70)

    for code, nome in STATIONS.items():
        print(f"\n--- {nome} ({code}) ---")
        items = buscar(code, hoje, token)
        print(f"  Recebidos: {len(items)}")

        if items:
            primeira = items[0].get("Data_Hora_Medicao")
            ultima = items[-1].get("Data_Hora_Medicao")
            print(f"  Periodo: {primeira} -> {ultima}")

            out = OUTPUT_DIR / f"{code}_{nome}.json"
            with out.open("w", encoding="utf-8") as f:
                json.dump(items, f, ensure_ascii=False, indent=2)
            print(f"  [OK] Salvo: {out.name} ({out.stat().st_size/1024:.0f} KB)")
        time.sleep(0.5)

    print("\n" + "=" * 70)
    print("  FIM")
    print("=" * 70)
