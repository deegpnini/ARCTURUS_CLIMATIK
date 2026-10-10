import csv
from pathlib import Path
from datetime import datetime
import numpy as np

# Ler
def ler(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

# Tubarao — da telemetria 2026
import json
with open("data/telemetria_84580000_2026.json", encoding="utf-8") as f:
    tub = json.load(f).get("items") or []

# Indexa por timestamp
def indexar(rows, key="Data_Hora_Medicao", val="Cota_Adotada"):
    out = {}
    for r in rows:
        ts = r.get(key)
        v = r.get(val)
        if ts and v not in (None, ""):
            try:
                out[ts] = float(v)
            except:
                pass
    return out

# Tubarao
tub_dict = {}
for r in tub:
    ts = r.get("Data_Hora_Medicao")
    v = r.get("Cota_Adotada")
    if ts and v not in (None, ""):
        try:
            tub_dict[ts] = float(v)
        except:
            pass

# Sao Mauricio e Rio Fortuna
sm = indexar(ler(Path("data/consolidado/84538500_SAO_MAURICIO_JUSANTE_consolidado.csv")))
rf = indexar(ler(Path("data/consolidado/84536000_RIO_FORTUNA_JUSANTE_consolidado.csv")))

print(f"Tubarao: {len(tub_dict)} leituras")
print(f"Sao Mauricio: {len(sm)} leituras")
print(f"Rio Fortuna: {len(rf)} leituras")
print()

# Timestamps comuns entre Tubarao e cada candidata
# Tenta varios lags (em horas)
def testar_lag(tub, cand, lag_horas, nome):
    # Shifta tub por lag
    # Se lag > 0: correlaciona cand(t) com tub(t + lag)
    # Se lag < 0: correlaciona cand(t) com tub(t - |lag|)
    from datetime import timedelta

    # Encontra timestamps do Tubarao
    tub_ts = {datetime.fromisoformat(t.replace(".0", "")): v for t, v in tub.items() if len(t) >= 19}

    # Pra cada lag, alinha
    pares = []
    for ts_str, cand_val in cand.items():
        try:
            ts = datetime.fromisoformat(ts_str.replace(".0", ""))
        except:
            continue
        # Tubarao no timestamp alvo
        alvo = ts + timedelta(hours=lag_horas)
        # Encontra leitura mais proxima em Tubarao (±5 min)
        best = None
        best_delta = 300
        for tub_ts_key, tub_val in tub_ts.items():
            delta = abs((tub_ts_key - alvo).total_seconds())
            if delta < best_delta:
                best_delta = delta
                best = tub_val
        if best is not None:
            pares.append((cand_val, best))

    if len(pares) < 50:
        return None

    cands = np.array([p[0] for p in pares])
    tubs = np.array([p[1] for p in pares])

    # Correlacao de Pearson
    if cands.std() == 0 or tubs.std() == 0:
        return 0

    corr = np.corrcoef(cands, tubs)[0, 1]
    return corr, len(pares)

# Testa lag -12 a +12 (em horas)
print("=== Correlacao Sao Mauricio vs Tubarao ===")
print(f"{'Lag (h)':>8} {'Corr':>10} {'N':>8}")
melhor_sm = (None, 0)
for lag in range(-12, 13):
    r = testar_lag(tub_dict, sm, lag, "SM")
    if r:
        corr, n = r
        print(f"{lag:>8} {corr:>10.4f} {n:>8}")
        if abs(corr) > abs(melhor_sm[1]):
            melhor_sm = (lag, corr)

print(f"\nMelhor lag Sao Mauricio: {melhor_sm[0]}h (corr={melhor_sm[1]:.4f})")

print()
print("=== Correlacao Rio Fortuna vs Tubarao ===")
print(f"{'Lag (h)':>8} {'Corr':>10} {'N':>8}")
melhor_rf = (None, 0)
for lag in range(-12, 13):
    r = testar_lag(tub_dict, rf, lag, "RF")
    if r:
        corr, n = r
        print(f"{lag:>8} {corr:>10.4f} {n:>8}")
        if abs(corr) > abs(melhor_rf[1]):
            melhor_rf = (lag, corr)

print(f"\nMelhor lag Rio Fortuna: {melhor_rf[0]}h (corr={melhor_rf[1]:.4f})")
