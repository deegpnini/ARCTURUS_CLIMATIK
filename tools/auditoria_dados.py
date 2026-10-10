import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
L = []
def p(x=""):
    print(x); L.append(str(x))

def carregar(path):
    d = json.load(open(path, encoding="utf-8"))
    its = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
    df = pd.DataFrame(its)
    df["t"] = pd.to_datetime(df["Data_Hora_Medicao"].astype(str).str.replace("T", " ").str[:19])
    for c in ("Cota_Adotada", "Chuva_Adotada", "Vazao_Adotada", "Cota_Adotada_Status"):
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df.set_index("t")

arqs = sorted((ROOT / "data/_backup/cache").glob("telemetria_84580000_*.json"))
if not arqs:
    arqs = [ROOT / "data/telemetria_84580000_2026.json"]
p("arquivos: " + ", ".join(a.name for a in arqs))
df = pd.concat([carregar(a) for a in arqs]).sort_index()
df = df[~df.index.duplicated(keep="last")]
st = df["Cota_Adotada_Status"]
p(f"registros: {len(df)} | de {df.index.min()} a {df.index.max()}")

p("\n== 1. COBERTURA MENSAL DA COTA (ultimo mes e parcial) ==")
g = pd.Grouper(freq="MS")
m = pd.DataFrame({"linhas": df.groupby(g).size(),
                  "cota_valida": df["Cota_Adotada"].groupby(g).count(),
                  "status1": (st == 1).groupby(g).sum()})
m["slots"] = m.index.days_in_month * 96
m["cobertura_%"] = (100 * m["cota_valida"] / m["slots"]).round(0).astype(int)
p(m.to_string())

p("\n== 2. STATUS x COTA ==")
p(pd.crosstab(st.fillna(-1).rename("status (-1 = vazio)"), df["Cota_Adotada"].notna().rename("tem_cota")).to_string())
s1 = df[st == 1]
if len(s1):
    p(f"\nstatus=1: {len(s1)} linhas, de {s1.index.min()} a {s1.index.max()}")
    p(s1["Cota_Adotada"].describe().round(1).to_string())
    p(s1[["Cota_Adotada", "Vazao_Adotada", "Chuva_Adotada"]].head(6).to_string())

p("\n== 3. COBERTURA DAS JANELAS DO SPLIT (dataset_1h) ==")
ds = pd.read_csv(ROOT / "data/dataset_1h.csv", usecols=["timestamp"])
ds["timestamp"] = pd.to_datetime(ds["timestamp"])
hs = json.load(open(ROOT / "data/split_v3.json", encoding="utf-8"))["historico"]
jan = {"treino": (ds["timestamp"].min(), pd.Timestamp(hs[17]["fim"])),
       "val": (pd.Timestamp(hs[18]["inicio"]), pd.Timestamp(hs[21]["fim"])),
       "teste": (pd.Timestamp(hs[22]["inicio"]), pd.Timestamp(hs[26]["fim"]))}
for nome, (a, b) in jan.items():
    n = int(ds["timestamp"].between(a, b).sum())
    esp = int((b - a) / pd.Timedelta("15min")) + 1
    p(f"{nome:6s} {a} a {b} | linhas={n} | slots={esp} | cobertura={100 * n / esp:.0f}%")
if len(s1):
    p("linhas do dataset em timestamps com status=1: " + str(int(ds["timestamp"].isin(s1.index).sum())))

p("\n== 4. CHUVA: INCREMENTO OU ACUMULADO? ==")
c = df["Chuva_Adotada"].dropna()
dif = c.diff()
dif = dif[c.index.to_series().diff() == pd.Timedelta("15min")]
neg = dif[dif < 0]
p(f"passos consecutivos: {len(dif)} | quedas: {len(neg)} ({100 * len(neg) / max(len(dif), 1):.1f}%)")
p("minuto da hora das quedas:")
p(neg.index.minute.value_counts().sort_index().to_string())

p("\n== 5. teste_446_delta.json ==")
for q in (ROOT / "resultados/teste_446_delta.json", ROOT / "data/referencia/teste_446_delta.json"):
    if q.exists():
        p(f"-- {q.relative_to(ROOT)}")
        p(q.read_text(encoding="utf-8")[:3000])

(ROOT / "resultados").mkdir(exist_ok=True)
(ROOT / "resultados/auditoria_dados.txt").write_text("\n".join(L), encoding="utf-8")
p("\n[OK] salvo em resultados/auditoria_dados.txt")
