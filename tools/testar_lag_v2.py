"""
Analise de lag CORRIGIDA.
- Alinhamento por timestamp (pandas merge_asof)
- Correlacao de NIVEIS e de VARIACOES
- Filtra pares com gap > 5 min
"""
import json
import pandas as pd
from pathlib import Path

# ============================================================
# Carregar
# ============================================================
def ler_csv(path, code):
    df = pd.read_csv(path, encoding="utf-8-sig")
    df["Data_Hora_Medicao"] = pd.to_datetime(df["Data_Hora_Medicao"], errors="coerce")
    df["Cota_Adotada"] = pd.to_numeric(df["Cota_Adotada"], errors="coerce")
    df = df.dropna(subset=["Data_Hora_Medicao", "Cota_Adotada"])
    df = df.rename(columns={"Cota_Adotada": code})
    return df[["Data_Hora_Medicao", code]].sort_values("Data_Hora_Medicao").reset_index(drop=True)

# Tubarao (JSON)
with open("data/telemetria_84580000_2026.json", encoding="utf-8") as f:
    tub_items = json.load(f).get("items") or []
tub = pd.DataFrame([
    {"Data_Hora_Medicao": it.get("Data_Hora_Medicao"), "cota": it.get("Cota_Adotada")}
    for it in tub_items
])
tub["Data_Hora_Medicao"] = pd.to_datetime(tub["Data_Hora_Medicao"], errors="coerce")
tub["cota"] = pd.to_numeric(tub["cota"], errors="coerce")
tub = tub.dropna().sort_values("Data_Hora_Medicao").reset_index(drop=True)

sm = ler_csv("data/consolidado/84538500_SAO_MAURICIO_JUSANTE_consolidado.csv", "sm")
rf = ler_csv("data/consolidado/84536000_RIO_FORTUNA_JUSANTE_consolidado.csv", "rf")

print(f"Tubarao: {len(tub)} leituras | {tub['Data_Hora_Medicao'].min()} -> {tub['Data_Hora_Medicao'].max()}")
print(f"Sao Mauricio: {len(sm)} leituras | {sm['Data_Hora_Medicao'].min()} -> {sm['Data_Hora_Medicao'].max()}")
print(f"Rio Fortuna: {len(rf)} leituras | {rf['Data_Hora_Medicao'].min()} -> {rf['Data_Hora_Medicao'].max()}")

# ============================================================
# Testa lag com merge_asof
# ============================================================
def testar_lag(tub_df, cand_df, cand_col, lag_horas):
    # Desloca os timestamps do Tubarao
    tub_lag = tub_df.copy()
    tub_lag["ts_alvo"] = tub_lag["Data_Hora_Medicao"] + pd.Timedelta(hours=lag_horas)
    tub_lag = tub_lag[["ts_alvo", "cota"]].rename(columns={"cota": "tub"}).sort_values("ts_alvo")

    cand = cand_df.copy().rename(columns={cand_col: "cand"}).sort_values("Data_Hora_Medicao")

    # merge_asof: pra cada cand, acha o tub mais proximo em ts_alvo (tolerancia 5 min)
    merged = pd.merge_asof(
        cand,
        tub_lag,
        left_on="Data_Hora_Medicao",
        right_on="ts_alvo",
        direction="nearest",
        tolerance=pd.Timedelta(minutes=5),
    )
    merged = merged.dropna(subset=["cand", "tub"])
    if len(merged) < 50:
        return None
    return merged

def correlacao_niveis(merged):
    return merged["cand"].corr(merged["tub"])

def correlacao_variacoes(merged):
    # Ordena por tempo
    m = merged.sort_values("Data_Hora_Medicao").reset_index(drop=True)
    # Delta dentro do proprio dataframe (intervalos maiores que 5 min = quebra)
    delta_time = m["Data_Hora_Medicao"].diff()
    delta_cand = m["cand"].diff()
    delta_tub = m["tub"].diff()
    # So considera pares onde o intervalo foi curto (< 90 min)
    mask = delta_time < pd.Timedelta(minutes=90)
    dc = delta_cand[mask].dropna()
    dt = delta_tub[mask].dropna()
    if len(dc) < 50:
        return None
    return dc.corr(dt), len(dc)

# ============================================================
# Roda pra cada estacao
# ============================================================
for nome, df, col in [("SAO MAURICIO", sm, "sm"), ("RIO FORTUNA", rf, "rf")]:
    print(f"\n{'='*70}")
    print(f"{nome} vs TUBARAO")
    print(f"{'='*70}")
    print(f"{'Lag':>4} | {'Corr_nivel':>10} | {'N':>6} | {'Corr_delta':>10} | {'N_delta':>8}")
    print("-" * 70)

    melhor_nivel = (None, 0)
    melhor_delta = (None, 0)

    for lag in range(-12, 13):
        merged = testar_lag(tub, df, col, lag)
        if merged is None:
            print(f"{lag:>4} | (poucos pares)")
            continue
        cn = correlacao_niveis(merged)
        cd = correlacao_variacoes(merged)
        if cd is None:
            print(f"{lag:>4} | {cn:>10.4f} | {len(merged):>6} | (poucos deltas)")
            if abs(cn) > abs(melhor_nivel[1]):
                melhor_nivel = (lag, cn)
            continue
        cd_val, cd_n = cd
        print(f"{lag:>4} | {cn:>10.4f} | {len(merged):>6} | {cd_val:>10.4f} | {cd_n:>8}")
        if abs(cn) > abs(melhor_nivel[1]):
            melhor_nivel = (lag, cn)
        if abs(cd_val) > abs(melhor_delta[1]):
            melhor_delta = (lag, cd_val)

    print()
    print(f"Melhor lag (NIVEL):   {melhor_nivel[0]}h  corr={melhor_nivel[1]:.4f}")
    print(f"Melhor lag (DELTA):   {melhor_delta[0]}h  corr={melhor_delta[1]:.4f}")
