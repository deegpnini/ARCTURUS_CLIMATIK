import json, math, sys, urllib.request, urllib.parse, urllib.error
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
ANCORA, RAIO_KM = "84580000", 100
URL = "https://www.ana.gov.br/hidrowebservice/EstacoesTelemetricas/HidroinfoanaSerieTelemetricaAdotada/v1"

inv = json.load(open(ROOT / "data/ana_inventario_sc.json", encoding="utf-8"))
items = inv if isinstance(inv, list) else next(v for v in inv.values() if isinstance(v, list))
por_cod = {str(i["codigoestacao"]): i for i in items}
a = por_cod.get(ANCORA)
if not a: sys.exit(f"ancora {ANCORA} fora do inventario")

def f(x):
    try: return float(x)
    except (TypeError, ValueError): return None
lat0, lon0 = f(a["Latitude"]), f(a["Longitude"])

def km(i):
    la, lo = f(i.get("Latitude")), f(i.get("Longitude"))
    if None in (la, lo, lat0, lon0): return None
    p = math.pi / 180
    h = math.sin((la - lat0) * p / 2) ** 2 + math.cos(lat0 * p) * math.cos(la * p) * math.sin((lo - lon0) * p / 2) ** 2
    return 12742 * math.asin(math.sqrt(h))

print("ANCORA:", a["codigoestacao"], a["Estacao_Nome"], "| rio:", a["Rio_Nome"], "| area:", a.get("Area_Drenagem"),
      "| telem:", a.get("Tipo_Estacao_Telemetrica"), "| operando:", a.get("Operando"))
cand = []
for i in items:
    if i.get("Tipo_Estacao") != "Fluviometrica": continue
    if i.get("Tipo_Estacao_Telemetrica") != "1" or i.get("Tipo_Estacao_Escala") != "1": continue
    if i.get("Data_Periodo_Telemetrica_Fim"): continue
    d = km(i)
    if d is not None and d <= RAIO_KM: cand.append((d, i))
cand.sort(key=lambda t: t[0])
print(f"\n{len(cand)} candidatas ate {RAIO_KM} km (ordenadas por distancia; distancia NAO prova montante)\n")
print(f"{'km':>5} {'codigo':9} {'estacao':34} {'rio':20} {'area':>7} {'telem desde':11} {'oper':>5} op")
for d, i in cand:
    print(f"{d:5.0f} {i['codigoestacao']:9} {str(i['Estacao_Nome'])[:34]:34} {str(i['Rio_Nome'])[:20]:20} "
          f"{str(i.get('Area_Drenagem') or '-'):>7} {str(i.get('Data_Periodo_Telemetrica_Inicio') or '')[:10]:11} "
          f"{str(i.get('Operando')):>5} {i.get('Operadora_Sigla')}")

if "--vivo" in sys.argv:
    try: from ana_auth import get_token
    except ImportError: from src.coleta.ana_auth import get_token
    tok = get_token()
    print("\n--- VIVO (ultimos 30 dias) ---")
    for cod in [ANCORA] + [str(i["codigoestacao"]) for _, i in cand]:
        q = urllib.parse.urlencode({"Código da Estação": cod, "Tipo Filtro Data": "DATA_LEITURA",
                                    "Range Intervalo de busca": "DIAS_30"}, quote_via=urllib.parse.quote)
        try:
            req = urllib.request.Request(f"{URL}?{q}", headers={"Authorization": f"Bearer {tok}"})
            with urllib.request.urlopen(req, timeout=60) as r:
                its = json.loads(r.read().decode("utf-8")).get("items") or []
        except urllib.error.HTTPError as e:
            print(cod, "HTTP", e.code); continue
        except Exception as e:
            print(cod, "erro", str(e)[:60]); continue
        ts = [x.get("Data_Hora_Medicao") for x in its if x.get("Data_Hora_Medicao")]
        n_cota = sum(1 for x in its if x.get("Cota_Adotada") not in (None, ""))
        n_ch = sum(1 for x in its if x.get("Chuva_Adotada") not in (None, ""))
        print(f"{cod}  n={len(its):5d}  cota={n_cota:5d}  chuva={n_ch:5d}  ultima={max(ts) if ts else '-'}")
