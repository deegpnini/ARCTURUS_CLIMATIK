"""
Baixa histórico longo (2 anos) das estacoes a montante do Tubarao.
Consulta em blocos de 29 dias (limite ANA e 30).
Salva CSV + JSON por estacao em data/historico_montante/.
"""
import csv
import json
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import quote
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

# ============================================================
# CONFIGURACAO
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parents[1]

API_URL = (
    "https://www.ana.gov.br/hidrowebservice/"
    "EstacoesTelemetricas/"
    "HidroinfoanaSerieTelemetricaAdotada/v1"
)

HISTORY_DAYS = 730  # 2 anos
END_DATE = date.today()
START_DATE = END_DATE - timedelta(days=HISTORY_DAYS)

REQUEST_DELAY_SECONDS = 0.5
REQUEST_TIMEOUT_SECONDS = 90

STATIONS = {
    "84249998": "ORLEANS_MONTANTE",
    "84538500": "SAO_MAURICIO_JUSANTE",
    "84536000": "RIO_FORTUNA_JUSANTE",
}

OUTPUT_DIR = PROJECT_ROOT / "data" / "historico_montante"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from ana_auth import get_token

# ============================================================
# FUNCOES
# ============================================================
def consultar_bloco(code: str, data_inicio: str, token: str):
    """
    Consulta 29 dias a partir de data_inicio (yyyy-MM-dd).
    Retorna lista de items ou None em caso de erro.
    """
    params = {
        "Codigo da Estacao": code,
        "Tipo Filtro Data": "DATA_LEITURA",
        "Range Intervalo de busca": "DIAS_30",
        "Data de Busca (yyyy-MM-dd)": data_inicio,
    }
    # URL-encode manual (nomes com espaco e acento)
    query = (
        "C%C3%B3digo%20da%20Esta%C3%A7%C3%A3o=" + quote(code) +
        "&Tipo%20Filtro%20Data=DATA_LEITURA" +
        "&Range%20Intervalo%20de%20busca=DIAS_30" +
        "&Data%20de%20Busca%20(yyyy-MM-dd)=" + data_inicio
    )
    url = f"{API_URL}?{query}"
    req = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT_SECONDS) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data.get("code") != 200:
                print(f"    [AVISO] code={data.get('code')} message={data.get('message')}")
                return None
            return data.get("items") or []
    except HTTPError as e:
        print(f"    [HTTP {e.code}] {data_inicio}")
        return None
    except URLError as e:
        print(f"    [URL erro] {e}")
        return None
    except Exception as e:
        print(f"    [erro] {e}")
        return None


def baixar_estacao(code: str, nome: str, token: str):
    """
    Baixa 2 anos da estacao em blocos de 29 dias.
    Deduplica por Data_Hora_Medicao.
    Retorna lista ordenada de registros unicos.
    """
    print(f"\n{'='*70}")
    print(f"Baixando {nome} ({code})")
    print(f"Periodo: {START_DATE} a {END_DATE}")
    print(f"{'='*70}")

    records = {}
    bloco_atual = END_DATE
    total_blocos = 0

    while bloco_atual >= START_DATE:
        total_blocos += 1
        data_busca = (bloco_atual - timedelta(days=29)).strftime("%Y-%m-%d")

        print(f"  Bloco {total_blocos}: busca {data_busca} (ref: {bloco_atual})", flush=True)

        items = consultar_bloco(code, data_busca, token)

        if items is None:
            print(f"    [FALHA] pulando bloco")
            bloco_atual -= timedelta(days=29)
            time.sleep(REQUEST_DELAY_SECONDS)
            continue

        novos = 0
        for item in items:
            ts = item.get("Data_Hora_Medicao")
            if not ts:
                continue
            key = (code, str(ts))
            if key not in records:
                records[key] = item
                novos += 1

        # Info do bloco
        datas = [str(i.get("Data_Hora_Medicao")) for i in items if i.get("Data_Hora_Medicao")]
        if datas:
            print(f"    retornados={len(items)}, unicos_novos={novos}, acumulado={len(records)}")
            print(f"    periodo retornado: {min(datas)} -> {max(datas)}")

        bloco_atual -= timedelta(days=29)
        time.sleep(REQUEST_DELAY_SECONDS)

    # Ordena por timestamp
    rows = sorted(records.values(), key=lambda x: x.get("Data_Hora_Medicao", ""))

    print(f"\n  Total final: {len(rows)} registros unicos")
    if rows:
        print(f"  Primeira leitura: {rows[0].get('Data_Hora_Medicao')}")
        print(f"  Ultima leitura:   {rows[-1].get('Data_Hora_Medicao')}")

    return rows


def salvar_estacao(code: str, nome: str, rows: list):
    """Salva CSV + JSON por estacao."""
    if not rows:
        print(f"  [AVISO] sem dados pra {code}, nada salvo")
        return

    base = f"{code}_{nome}_{START_DATE}_{END_DATE}"
    csv_path = OUTPUT_DIR / f"{base}.csv"
    json_path = OUTPUT_DIR / f"{base}.json"

    # CSV
    fields = sorted({k for row in rows for k in row.keys()})
    with csv_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # JSON
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(rows, f, ensure_ascii=False, indent=2)

    print(f"  [OK] CSV:  {csv_path.name} ({csv_path.stat().st_size / 1024:.1f} KB)")
    print(f"  [OK] JSON: {json_path.name} ({json_path.stat().st_size / 1024:.1f} KB)")


# ============================================================
# MAIN
# ============================================================
if __name__ == "__main__":
    print("=" * 70)
    print("  ARCTURUS — Baixar historico a montante")
    print(f"  Periodo: {START_DATE} a {END_DATE} ({HISTORY_DAYS} dias)")
    print(f"  Estacoes: {len(STATIONS)}")
    print(f"  Requisicoes previstas: ~{len(STATIONS) * (HISTORY_DAYS // 29 + 1)}")
    print("=" * 70)

    token = get_token()
    print(f"\nToken: {len(token)} chars")

    for code, nome in STATIONS.items():
        rows = baixar_estacao(code, nome, token)
        salvar_estacao(code, nome, rows)

    print("\n" + "=" * 70)
    print("  FIM")
    print(f"  Arquivos em: {OUTPUT_DIR}")
    print("=" * 70)
