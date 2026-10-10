import csv
from pathlib import Path
from datetime import datetime
from collections import Counter

DIR = Path("data/historico_montante")

def auditar_csv(path):
    print(f"\n{'='*70}")
    print(f"ARQUIVO: {path.name}")
    print(f"{'='*70}")

    with path.open(encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"Registros: {len(rows)}")
    if not rows:
        return

    print(f"Colunas ({len(rows[0])}): {list(rows[0].keys())}")

    # Timestamps
    ts_col = "Data_Hora_Medicao"
    if ts_col in rows[0]:
        timestamps = [r[ts_col] for r in rows if r.get(ts_col)]
        print(f"\nTimestamps:")
        print(f"  Primeiro: {timestamps[0]}")
        print(f"  Ultimo:   {timestamps[-1]}")
        print(f"  Total:    {len(timestamps)}")

        # Conta intervalos entre leituras consecutivas
        datas = []
        for t in timestamps:
            try:
                datas.append(datetime.fromisoformat(t.replace(".0", "")))
            except:
                continue

        if len(datas) > 1:
            intervalos = [(datas[i+1] - datas[i]).total_seconds() / 60 for i in range(len(datas)-1)]
            contagem = Counter(round(i) for i in intervalos)
            print(f"\nIntervalos entre leituras (minutos):")
            for intervalo, n in contagem.most_common(8):
                print(f"  {intervalo:5d} min: {n:6d} vezes")

    # Colunas de cota e chuva
    for col in ["Cota_Adotada", "Chuva_Adotada", "Vazao_Adotada"]:
        if col in rows[0]:
            validos = sum(1 for r in rows if r.get(col) not in (None, "", "None"))
            print(f"\n{col}: {validos}/{len(rows)} ({validos*100//len(rows)}%)")

    # Gaps grandes (> 1 dia)
    if ts_col in rows[0] and len(datas) > 1:
        gaps = []
        for i in range(len(datas)-1):
            delta_h = (datas[i+1] - datas[i]).total_seconds() / 3600
            if delta_h > 24:
                gaps.append((datas[i], datas[i+1], delta_h))
        print(f"\nGaps > 24h: {len(gaps)}")
        for inicio, fim, h in gaps[:5]:
            print(f"  {inicio} -> {fim} ({h:.0f}h)")

# Roda pra cada CSV
for csv_file in sorted(DIR.glob("*.csv")):
    auditar_csv(csv_file)
