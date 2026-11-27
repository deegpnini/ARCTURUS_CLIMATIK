import io, json, subprocess, sys
import pandas as pd

JSONL = "data/historico_defesacivil_bacia.jsonl"
SQL = """COPY (SELECT episode_id, inicio_ts, subida_ts, pico_ts, cota_pico_cm, regime
FROM episodios_hidrologicos WHERE chuva_fonte = 'DEFESA_CIVIL_SC'
ORDER BY inicio_ts) TO STDOUT WITH CSV HEADER"""
ANTES_H, LIMIAR_MM = 48, 2.0

ep = pd.read_csv(
    io.StringIO(subprocess.check_output(["psql", "-d", "arcturus", "-c", SQL], text=True)),
    parse_dates=["inicio_ts", "subida_ts", "pico_ts"],
)

linhas = []
alt_amostra = {}
with open(JSONL, encoding="utf-8") as f:
    for i, ln in enumerate(f):
        if not ln.strip():
            continue
        d = json.loads(ln)
        if i == 0:
            print("chaves da 1ª linha:", list(d.keys()))
            if d.get("estacoes"):
                print("chaves da estação:", list(d["estacoes"][0].keys()))
        if "estacoes" not in d or "timestamp_coleta" not in d:
            sys.exit("esquema diferente do esperado; mande as chaves impressas acima")
        tc = pd.to_datetime(d["timestamp_coleta"])
        for e in d["estacoes"]:
            cod = e.get("codigo")
            if e.get("cota_altimetrica_m") is not None:
                alt_amostra.setdefault(cod, set()).add(e.get("cota_altimetrica_m"))
            linhas.append((
                tc,
                cod,
                e.get("trecho_bacia"),
                e.get("atualizacao_estacao"),
                e.get("chuva_1h_mm"),
            ))

print("valores distintos de cota_altimetrica_m por estação (amostra):",
      {k: sorted(list(v))[:5] for k, v in alt_amostra.items()})

df = pd.DataFrame(linhas, columns=["t_coleta", "codigo", "trecho", "t_leitura", "chuva_1h"])
df["t"] = pd.to_datetime(df.t_leitura, format="%d/%m/%Y %H:%M:%S", errors="coerce").fillna(df.t_coleta)
df = df.dropna(subset=["chuva_1h"]).drop_duplicates(["codigo", "t"]).sort_values("t")
print(f"cobertura: {df.t.min()} → {df.t.max()} | estações: {df.codigo.nunique()}")

res = []
for _, e in ep.iterrows():
    for cod, g in df.groupby("codigo"):
        w = g[(g.t >= e.subida_ts - pd.Timedelta(hours=ANTES_H)) & (g.t <= e.pico_ts)]
        if len(w) < 20 or w.chuva_1h.max() < LIMIAR_MM:
            res.append((
                e.episode_id, e.regime, cod, w.trecho.iloc[0] if len(w) else None,
                None, None, None, len(w), "sem_chuva_relevante_ou_lacuna",
            ))
            continue
        s = w.set_index("t").chuva_1h.rolling("3h").mean()
        tp = s.idxmax()
        res.append((
            e.episode_id, e.regime, cod, w.trecho.iloc[0], tp,
            (e.subida_ts - tp).total_seconds() / 3600,
            (e.pico_ts - tp).total_seconds() / 3600, len(w), "ok",
        ))

r = pd.DataFrame(
    res,
    columns=["episodio", "regime", "estacao", "trecho", "t_pico_chuva",
             "lag_subida_h", "lag_pico_h", "n_leituras", "flag"],
)
r.to_csv("data/lag_chuva_para_erab.csv", index=False)
ok = r[r.flag == "ok"]
print(r.to_string(index=False))
print("\nlag até o pico (h), mediana por estação:")
print(ok.groupby("estacao").lag_pico_h.agg(["count", "median", "min", "max"]).round(1))
