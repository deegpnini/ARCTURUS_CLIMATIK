import json
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
arqs = sorted((ROOT / "data/_backup/cache").glob("telemetria_84580000_*.json")) or [ROOT / "data/telemetria_84580000_2026.json"]
parts = []
for a in arqs:
    d = json.load(open(a, encoding="utf-8"))
    its = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
    df = pd.DataFrame(its)
    df["t"] = pd.to_datetime(df["Data_Hora_Medicao"].astype(str).str.replace("T", " ").str[:19])
    df["c"] = pd.to_numeric(df["Cota_Adotada"], errors="coerce")
    df["st"] = pd.to_numeric(df["Cota_Adotada_Status"], errors="coerce")
    parts.append(df[["t", "c", "st"]])
tel = pd.concat(parts).drop_duplicates("t", keep="last").set_index("t").sort_index()
ds = pd.read_csv(ROOT / "data/dataset_1h.csv", usecols=["timestamp"])
ds["timestamp"] = pd.to_datetime(ds["timestamp"])
hs = json.load(open(ROOT / "data/split_v3.json", encoding="utf-8"))["historico"]

print(f"eventos no split: {len(hs)}\n")
rows = []
for i, e in enumerate(hs):
    a, b = pd.Timestamp(e["inicio"]), pd.Timestamp(e["fim"])
    w = tel.loc[a:b]
    rows.append(dict(i=i, grupo="treino" if i <= 17 else ("val" if i <= 21 else "teste"), inicio=a.date(),
                     leit_cota=int(w["c"].notna().sum()), status1=int((w["st"] == 1).sum()),
                     cota_min=w["c"].min(), cota_max=w["c"].max(), pico_split=e.get("pico"),
                     linhas_ds=int(ds["timestamp"].between(a, b).sum())))
print(pd.DataFrame(rows).to_string(index=False))

print("\n== status por valor: distribuicao da cota ==")
print(tel.groupby(tel["st"].fillna(-1))["c"].describe().round(1).to_string())
s1 = tel["st"] == 1
print("\nstatus=1 por mes (so meses com ocorrencia):")
print(s1.groupby(pd.Grouper(freq="MS")).sum().loc[lambda x: x > 0].to_string())
grp = (s1 != s1.shift()).cumsum()
runs = s1.groupby(grp).agg(["first", "size"])
runs = runs[runs["first"]]["size"]
print(f"\nsequencias de status=1: {len(runs)} | tamanho mediano {runs.median():.0f} leituras | maior {runs.max()}")
tj = (pd.Timestamp(hs[22]["inicio"]), pd.Timestamp(hs[26]["fim"]))
print("status=1 dentro da janela de teste:", int(s1.loc[tj[0]:tj[1]].sum()))
