import sys
from pathlib import Path
import pandas as pd

PATH_ORLEANS = "data/consolidado/84249998_ORLEANS_MONTANTE_consolidado.csv"
CANDIDATOS_84580000 = [
    "data/consolidado/84580000_TUBARAO_JUSANTE_consolidado.csv",
    "data/consolidado/84580000_consolidado.csv",
    "data/ana_longa84580000.csv",
]

def escolher_coluna_hidro(df: pd.DataFrame, nome_fonte: str) -> str:
    v = [
        c for c in df.columns
        if any(k in c.lower() for k in ("vaz", "cota", "nivel", "level"))
        and "status" not in c.lower()
        and pd.to_numeric(df[c], errors="coerce").fillna(0).gt(0).any()
    ]
    if len(v) == 0:
        sys.exit(f"[{nome_fonte}] Nenhuma coluna de vazao/cota com valores > 0. Colunas: {list(df.columns)}")
    if len(v) > 1:
        sys.exit(f"[{nome_fonte}] Mais de uma coluna candidata com valores > 0: {v}")
    return v[0]

def carregar_serie_horaria(path_str: str, nome_fonte: str) -> tuple[pd.Series, str]:
    p = Path(path_str)
    if not p.exists():
        sys.exit(f"[{nome_fonte}] Arquivo nao encontrado: {path_str}")
    df = pd.read_csv(p, encoding="utf-8-sig")
    col_val = escolher_coluna_hidro(df, nome_fonte)

    col_ts = next((c for c in df.columns if "data" in c.lower() or "hora" in c.lower() or c.lower() in ("ts", "timestamp")), None)
    if not col_ts:
        sys.exit(f"[{nome_fonte}] Coluna de timestamp nao identificada em {list(df.columns)}")

    df["ts"] = pd.to_datetime(df[col_ts], errors="coerce")
    df["val"] = pd.to_numeric(df[col_val], errors="coerce")
    df = df.dropna(subset=["ts", "val"])
    df = df[df["val"] > 0]

    s = df.set_index("ts").sort_index()["val"].resample("1h").mean().dropna()
    return s, col_val

def localizar_84580000() -> str:
    for c in CANDIDATOS_84580000:
        if Path(c).exists():
            return c
    encontrados = sorted(str(p) for p in Path("data").rglob("*84580000*.csv"))
    if len(encontrados) == 1:
        return encontrados[0]
    sys.exit(f"[84580000] Informe o caminho exato; candidatos encontrados: {encontrados}")

path_jus = localizar_84580000()
s_orl, col_orl = carregar_serie_horaria(PATH_ORLEANS, "ORLEANS_84249998")
s_jus, col_jus = carregar_serie_horaria(path_jus, "TUBARAO_84580000")

print(f"Orleans ({col_orl}): n_h={len(s_orl)} | {s_orl.index.min()} -> {s_orl.index.max()}")
print(f"84580000 [{path_jus}] ({col_jus}): n_h={len(s_jus)} | {s_jus.index.min()} -> {s_jus.index.max()}")

# 1. Correlacao em serie suavizada (media movel 3h)
orl_sm = s_orl.rolling("3h", min_periods=2).mean()
jus_sm = s_jus.rolling("3h", min_periods=2).mean()

print("\n=== CORRELACAO EM SERIE SUAVIZADA (3h) ===")
melhor = None
for lag_h in range(0, 25):
    s_shift = orl_sm.copy()
    s_shift.index = s_shift.index + pd.Timedelta(hours=lag_h)
    par = pd.concat([s_shift.rename("orl"), jus_sm.rename("jus")], axis=1, sort=False).dropna()
    if len(par) >= 30 and par["orl"].std() > 0 and par["jus"].std() > 0:
        r_lvl = par["orl"].corr(par["jus"])
        r_anom = (par["orl"] - par["orl"].rolling("72h", min_periods=12).mean()).corr(
            par["jus"] - par["jus"].rolling("72h", min_periods=12).mean()
        )
        if melhor is None or (pd.notna(r_anom) and r_anom > melhor[1]):
            melhor = (lag_h, r_anom, r_lvl, len(par))
        if lag_h in (0, 2, 4, 6, 8, 10, 12, 15, 18, 24):
            print(f"  lag={lag_h:2d}h | n={len(par):5d} | r_suav={r_lvl:+.4f} | r_anom72h={r_anom:+.4f}")

if melhor:
    print(f"-> Pico r_anom72h: lag={melhor[0]}h (r_anom={melhor[1]:+.4f}, r_suav={melhor[2]:+.4f}, n={melhor[3]})")
else:
    print("-> Sem sobreposicao suficiente entre Orleans e 84580000.")

# 2. Defasagem por evento (pico de vazao em Orleans -> pico em 84580000 dentro de 0..24h)
par0 = pd.concat([orl_sm.rename("orl"), jus_sm.rename("jus")], axis=1, sort=False).dropna()
if len(par0) >= 30:
    limiar_p95 = par0["orl"].quantile(0.95)
    picos_orl = par0[
        (par0["orl"] >= limiar_p95)
        & (par0["orl"] == par0["orl"].rolling("25h", center=True, min_periods=1).max())
    ]
    eventos = []
    ultimo_t = None
    for t_orl, row in picos_orl.iterrows():
        if ultimo_t is not None and (t_orl - ultimo_t) < pd.Timedelta(hours=24):
            continue
        ultimo_t = t_orl
        jan_jus = jus_sm[(jus_sm.index >= t_orl) & (jus_sm.index <= t_orl + pd.Timedelta(hours=24))]
        if len(jan_jus) >= 6:
            t_jus = jan_jus.idxmax()
            lag_ev = (t_jus - t_orl).total_seconds() / 3600.0
            eventos.append((t_orl, round(row["orl"], 2), t_jus, round(jan_jus.max(), 2), round(lag_ev, 1)))
    df_ev = pd.DataFrame(eventos, columns=["t_pico_orleans", "vaz_pico_orl", "t_pico_84580000", "val_pico_jus", "lag_pico_h"])
    print(f"\n=== DEFASAGEM POR EVENTO (picos >= P95={limiar_p95:.2f} em Orleans, n={len(df_ev)}) ===")
    if not df_ev.empty:
        print(df_ev.to_string(index=False))
        print(df_ev["lag_pico_h"].agg(["count", "median", "min", "max"]).round(1).to_string())
