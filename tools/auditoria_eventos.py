import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
L = []
def p(x=""):
    print(x); L.append(str(x))

arqs = sorted((ROOT / "data/_backup/cache").glob("telemetria_84580000_*.json")) or [ROOT / "data/telemetria_84580000_2026.json"]
parts = []
for a in arqs:
    d = json.load(open(a, encoding="utf-8"))
    its = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
    df = pd.DataFrame(its)
    df["t"] = pd.to_datetime(df["Data_Hora_Medicao"].astype(str).str.replace("T", " ").str[:19])
    for c, n in (("Cota_Adotada", "c"), ("Chuva_Adotada", "chuva"), ("Vazao_Adotada", "vazao")):
        df[n] = pd.to_numeric(df[c], errors="coerce")
    parts.append(df[["t", "c", "chuva", "vazao"]])
tel = pd.concat(parts).drop_duplicates("t", keep="last").set_index("t").sort_index()
cota = tel["c"].dropna()

p("== 1. ALINHAMENTO DO ALVO (target_h == cota medida em t+h?) ==")
for h, k in (("1h", 60), ("3h", 180), ("6h", 360)):
    ds = pd.read_csv(ROOT / f"data/dataset_{h}.csv", usecols=["timestamp", "cota", f"target_{h}"])
    ds["timestamp"] = pd.to_datetime(ds["timestamp"])
    exp = cota.reindex(ds["timestamp"] + pd.Timedelta(minutes=k)).values
    comp = ~np.isnan(exp)
    ok = np.isclose(ds[f"target_{h}"].values, exp, atol=1e-6)
    okc = np.isclose(ds["cota"].values, cota.reindex(ds["timestamp"]).values, atol=1e-6, equal_nan=True)
    p(f"{h}: linhas={len(ds)} | comparaveis={int(comp.sum())} | alvo bate={100 * ok[comp].mean():.2f}% | cota(t) bate={100 * okc.mean():.2f}%")
    bad = ds[comp & ~ok].head(3000)
    if len(bad):
        cont = {}
        for off in range(15, 24 * 60 + 1, 15):
            e2 = cota.reindex(bad["timestamp"] + pd.Timedelta(minutes=off)).values
            cont[off] = int(np.isclose(bad[f"target_{h}"].values, e2, atol=1e-6).sum())
        p(f"   desalinhadas (amostra {len(bad)}). Deslocamentos que mais explicam (min:linhas): {sorted(cont.items(), key=lambda kv: -kv[1])[:3]}")

p("\n== 2. COBERTURA DENTRO DE CADA EVENTO (dataset_1h) ==")
hs = json.load(open(ROOT / "data/split_v3.json", encoding="utf-8"))["historico"]
p("chaves do evento 0: " + str(list(hs[0].keys())))
ds = pd.read_csv(ROOT / "data/dataset_1h.csv", usecols=["timestamp", "cota"])
ds["timestamp"] = pd.to_datetime(ds["timestamp"])
rows = []
for i, e in enumerate(hs):
    a, b = pd.Timestamp(e["inicio"]), pd.Timestamp(e["fim"])
    m = ds["timestamp"].between(a, b)
    slots = int((b - a) / pd.Timedelta("15min")) + 1
    pre = int(ds["timestamp"].between(a - pd.Timedelta("24h"), a).sum())
    rows.append(dict(i=i, grupo="treino" if i <= 17 else ("val" if i <= 21 else "teste"), inicio=a, fim=b,
                     linhas=int(m.sum()), slots=slots, cob=round(100 * m.sum() / max(slots, 1)),
                     cob_pre24h=round(100 * pre / 97), pico=float(ds.loc[m, "cota"].max()) if m.any() else np.nan))
ev = pd.DataFrame(rows)
p(ev.to_string(index=False))
p("\nmediana por grupo (%):"); p(ev.groupby("grupo")[["cob", "cob_pre24h"]].median().to_string())
p("eventos com cobertura < 80%: " + str(ev.loc[ev["cob"] < 80, "i"].tolist()))

p("\n== 3. LEITURAS VALIDAS POR MES (cota x chuva) ==")
g = pd.Grouper(freq="MS")
mm = pd.DataFrame({"cota": tel["c"].groupby(g).count(), "chuva": tel["chuva"].groupby(g).count(), "vazao": tel["vazao"].groupby(g).count()})
p(mm.loc["2025-10-01":"2026-09-01"].to_string())
(ROOT / "resultados").mkdir(exist_ok=True)
(ROOT / "resultados/auditoria_eventos.txt").write_text("\n".join(L), encoding="utf-8")
