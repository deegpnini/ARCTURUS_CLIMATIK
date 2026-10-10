import json
from pathlib import Path
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "resultados/retrospectiva_0922"
OUT.mkdir(parents=True, exist_ok=True)
L = []
def p(x=""):
    print(x); L.append(str(x))

d = json.load(open(ROOT / "data/telemetria_84580000_2026.json", encoding="utf-8"))
its = d if isinstance(d, list) else (d.get("items") or next(v for v in d.values() if isinstance(v, list)))
df = pd.DataFrame(its)
df["t"] = pd.to_datetime(df["Data_Hora_Medicao"].astype(str).str.replace("T", " ").str[:19])
for c in ("Cota_Adotada", "Chuva_Adotada", "Vazao_Adotada"):
    df[c] = pd.to_numeric(df[c], errors="coerce")
ndup = int(df["t"].duplicated().sum())
df = df.sort_values("t").drop_duplicates("t", keep="last").set_index("t")
df["atualizacao"] = pd.to_datetime(df["Data_Atualizacao"].astype(str).str.replace("T", " "), errors="coerce")
df["atraso_min"] = ((df["atualizacao"] - df.index.to_series()).dt.total_seconds() / 60).round(1)
p(f"registros: {len(df)} | duplicados removidos: {ndup} | periodo: {df.index.min()} a {df.index.max()}")

p("\n== A. Registros em torno do evento (atraso_min = Data_Atualizacao - medicao) ==")
cols = ["Cota_Adotada", "Cota_Adotada_Status", "Vazao_Adotada", "Chuva_Adotada", "atraso_min"]
p(df.loc["2026-09-21 19:00":"2026-09-22 02:00", cols].to_string())
p("\nStatus da cota (arquivo todo):")
p(df["Cota_Adotada_Status"].value_counts(dropna=False).to_string())

s = df["Cota_Adotada"].dropna().loc["2026-09-18":"2026-09-26"]
t_ant = s.loc[:"2026-09-21 23:59"].index[-1]
t_dep = s.loc["2026-09-22 00:00":].index[0]
faltam = int((t_dep - t_ant) / pd.Timedelta("15min")) - 1
g = df["Cota_Adotada"].loc["2026-09-18":"2026-09-26"].reindex(pd.date_range("2026-09-18", "2026-09-26 23:45", freq="15min"))
h1 = pd.Timedelta("1h")

p("\n== B. O buraco e o pico ==")
p(f"ultima leitura antes: {t_ant} = {s.loc[t_ant]:.0f} cm")
p(f"primeira leitura depois: {t_dep} = {s.loc[t_dep]:.0f} cm")
p(f"duracao: {(t_dep - t_ant) / h1:.2f} h | leituras sem cota: {faltam}")
p(f"maior valor medido em 18-26/09: {s.max():.0f} cm em {s.idxmax()}")
v0 = g.get(t_ant - pd.Timedelta("45min"))
if pd.notna(v0):
    p(f"subida nas ultimas leituras antes do buraco: {(s.loc[t_ant] - v0) / 3:.1f} cm/15min (~{(s.loc[t_ant] - v0) * 4 / 3:.0f} cm/h)")
p(f"subida media necessaria no buraco: {(s.loc[t_dep] - s.loc[t_ant]) / ((t_dep - t_ant) / h1):.0f} cm/h")
r1 = g.get(t_dep + h1)
if pd.notna(r1):
    p(f"recessao na 1a hora apos o buraco: {s.loc[t_dep] - r1:.0f} cm/h")

p("\n== C. Conferencia dos numeros do relatorio (erro da persistencia a partir de 446 cm) ==")
ref = {1: 22, 3: 33, 6: 71}
for h in (1, 3, 6):
    ts = t_dep + pd.Timedelta(hours=h)
    alvo = g.get(ts)
    if pd.isna(alvo):
        p(f"+{h}h ({ts}): sem leitura"); continue
    err = abs(s.loc[t_dep] - alvo)
    p(f"+{h}h ({ts}): observado={alvo:.0f} | erro persistencia={err:.0f} | relatorio cita={ref[h]} -> {'OK' if abs(err - ref[h]) <= 1 else 'DIFERE'}")

p("\n== D. Chuva_Adotada antes do primeiro dado apos o buraco (definicao do campo NAO verificada) ==")
c = df["Chuva_Adotada"]
for h in (6, 24, 48):
    w = c.loc[t_dep - pd.Timedelta(hours=h):t_dep]
    p(f"{h:2d}h: leituras validas={int(w.notna().sum()):4d} soma={w.sum():8.1f} max={w.max():6.1f}")
p("se o campo for ACUMULADO (e nao incremento), a soma nao vale; veja os valores da tabela A")

p("\n== E. A vazao e funcao da cota? ==")
v = df[["Cota_Adotada", "Vazao_Adotada"]].dropna()
agr = v.groupby("Cota_Adotada")["Vazao_Adotada"].agg(["count", "std", "max"])
agr = agr[(agr["count"] >= 5) & (agr["max"] > 0)]
rel = (agr["std"] / agr["max"]).median()
p(f"dispersao relativa mediana da vazao para a MESMA cota: {rel:.4f}  (perto de 0 = vazao derivada da cota, feature redundante)")
try:
    p(f"correlacao de Spearman cota x vazao: {v['Cota_Adotada'].corr(v['Vazao_Adotada'], method='spearman'):.4f}")
except Exception as e:
    p(f"spearman indisponivel: {e}")

fig, ax = plt.subplots(figsize=(11, 5))
w = g.loc["2026-09-20 12:00":"2026-09-23 12:00"]
ax.plot(w.index, w.values, lw=1.6, marker=".", ms=3, label="cota medida (15 min)")
ax.axvspan(t_ant, t_dep, color="gray", alpha=0.25, label=f"sem leituras ({faltam})")
ax.scatter([t_ant, t_dep], [s.loc[t_ant], s.loc[t_dep]], color="red", zorder=5)
ax.annotate(f"{s.loc[t_ant]:.0f} cm", (t_ant, s.loc[t_ant]), textcoords="offset points", xytext=(-40, 8))
ax.annotate(f"{s.loc[t_dep]:.0f} cm (ja em recessao)", (t_dep, s.loc[t_dep]), textcoords="offset points", xytext=(8, 8))
ax.set_title("Rio do Pouso (84580000) - 21-22/09/2026: pico real caiu no intervalo sem dados")
ax.set_ylabel("cota (cm)"); ax.grid(alpha=0.3); ax.legend(loc="upper right")
fig.savefig(OUT / "hidrograma_0922.png", dpi=150, bbox_inches="tight")

pd.DataFrame({"cota": g, "chuva": c.reindex(g.index), "vazao": df["Vazao_Adotada"].reindex(g.index)}).to_csv(
    OUT / "serie_18_26_set.csv", index_label="t", encoding="utf-8")
p("\n== F. Pendencias externas ==")
p("1) boletim Epagri/Ciram de 21 a 23/09 (estacao 84580000): comparar com a tabela A")
p("2) pedir a Epagri/Ciram ou ANA os dados do datalogger de 21/09 20:00 a 22/09 00:00")
(OUT / "RESUMO.txt").write_text("\n".join(L), encoding="utf-8")
p(f"\n[OK] salvo em {OUT}")
