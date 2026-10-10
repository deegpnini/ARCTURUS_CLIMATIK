import csv
from pathlib import Path
from datetime import datetime

# Ler os 3 CSVs consolidados
def ler(path):
    with path.open(encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

saomauricio = ler(Path("data/consolidado/84538500_SAO_MAURICIO_JUSANTE_consolidado.csv"))
riofortuna = ler(Path("data/consolidado/84536000_RIO_FORTUNA_JUSANTE_consolidado.csv"))
orleans = ler(Path("data/consolidado/84249998_ORLEANS_MONTANTE_consolidado.csv"))

# Filtro: evento 20-25/09/2026 (o evento do 446cm)
def filtro_evento(rows):
    out = []
    for r in rows:
        ts = r.get("Data_Hora_Medicao", "")
        if ts and "2026-09-2" in ts[:11]:
            out.append(r)
    return out

saomauricio_ev = filtro_evento(saomauricio)
riofortuna_ev = filtro_evento(riofortuna)
orleans_ev = filtro_evento(orleans)

print("=" * 70)
print("EVENTO 20-25/09/2026 (o do pico de 446 cm em Tubarao)")
print("=" * 70)
print()

# Sao Mauricio
print(f"--- SAO MAURICIO (n={len(saomauricio_ev)}) ---")
cotas_sm = [float(r["Cota_Adotada"]) for r in saomauricio_ev if r.get("Cota_Adotada") not in (None, "")]
if cotas_sm:
    print(f"  Cota min:  {min(cotas_sm):.2f}")
    print(f"  Cota max:  {max(cotas_sm):.2f}")
    print(f"  Variacao:  {max(cotas_sm) - min(cotas_sm):.2f}")
    print(f"  1a: {cotas_sm[0]:.2f}")
    print(f"  Ult: {cotas_sm[-1]:.2f}")

# Rio Fortuna
print()
print(f"--- RIO FORTUNA (n={len(riofortuna_ev)}) ---")
cotas_rf = [float(r["Cota_Adotada"]) for r in riofortuna_ev if r.get("Cota_Adotada") not in (None, "")]
if cotas_rf:
    print(f"  Cota min:  {min(cotas_rf):.2f}")
    print(f"  Cota max:  {max(cotas_rf):.2f}")
    print(f"  Variacao:  {max(cotas_rf) - min(cotas_rf):.2f}")
    print(f"  1a: {cotas_rf[0]:.2f}")
    print(f"  Ult: {cotas_rf[-1]:.2f}")

# Orleans (chuva)
print()
print(f"--- ORLEANS (n={len(orleans_ev)}) — CHUVA ---")
chuvas_or = [float(r["Chuva_Adotada"]) for r in orleans_ev if r.get("Chuva_Adotada") not in (None, "")]
if chuvas_or:
    print(f"  Chuva max: {max(chuvas_or):.2f} mm")
    print(f"  Chuva acumulada: {sum(chuvas_or):.2f} mm")

# Mostra timestamp das cotas max (quando ocorreu o pico)
print()
print("=== Onde ocorreu o pico ===")
if cotas_sm:
    max_idx = cotas_sm.index(max(cotas_sm))
    ts_pico = saomauricio_ev[max_idx]["Data_Hora_Medicao"]
    print(f"Sao Mauricio pico ({max(cotas_sm):.2f}) em: {ts_pico}")

if cotas_rf:
    max_idx = cotas_rf.index(max(cotas_rf))
    ts_pico = riofortuna_ev[max_idx]["Data_Hora_Medicao"]
    print(f"Rio Fortuna pico ({max(cotas_rf):.2f}) em: {ts_pico}")
