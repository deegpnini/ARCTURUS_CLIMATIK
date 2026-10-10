"""
Auditoria pandas dos 3 CSVs consolidados.
Le, conta, mede lacunas, valores ausentes, distribuicao diaria.
Nao modifica os originais.
"""
import pandas as pd
import numpy as np
from pathlib import Path

DIR = Path("data/consolidado")

def auditar(path):
    print(f"\n{'='*78}")
    print(f"ARQUIVO: {path.name}")
    print(f"{'='*78}")

    df = pd.read_csv(path, parse_dates=["Data_Hora_Medicao"])
    df = df.sort_values("Data_Hora_Medicao").reset_index(drop=True)

    print(f"Registros: {len(df)}")
    print(f"Colunas: {list(df.columns)}")

    # Periodo
    primeira = df["Data_Hora_Medicao"].min()
    ultima = df["Data_Hora_Medicao"].max()
    span_dias = (ultima - primeira).days
    print(f"\nPeriodo:")
    print(f"  Primeira: {primeira}")
    print(f"  Ultima:   {ultima}")
    print(f"  Duracao:  {span_dias} dias")

    # Duplicatas
    dup = df["Data_Hora_Medicao"].duplicated().sum()
    print(f"\nDuplicatas por timestamp: {dup}")

    # Intervalo entre leituras
    deltas = df["Data_Hora_Medicao"].diff().dt.total_seconds() / 60
    deltas = deltas.dropna()
    print(f"\nIntervalo entre leituras (min):")
    print(f"  mediana: {deltas.median():.0f}")
    print(f"  moda:    {deltas.mode().iloc[0]:.0f}")
    print(f"  max:     {deltas.max():.0f}")

    # Cobertura diaria
    df["dia"] = df["Data_Hora_Medicao"].dt.date
    dias_com_dado = df["dia"].nunique()
    print(f"\nCobertura diaria:")
    print(f"  dias com dado: {dias_com_dado} de {span_dias} ({dias_com_dado*100//span_dias}%)")

    # Valores ausentes
    print(f"\nValores ausentes por coluna:")
    for col in df.columns:
        if col in ["Data_Hora_Medicao", "dia"]:
            continue
        nulos = df[col].isna().sum()
        # Tenta converter pra numérico
        try:
            vals = pd.to_numeric(df[col], errors="coerce")
            validos = vals.notna().sum()
            print(f"  {col:35s}: {validos:6d}/{len(df)} ({validos*100//len(df)}%)")
        except:
            print(f"  {col:35s}: {nulos} nulos (nao-numerico)")

    # Gaps grandes
    gaps = []
    for i in range(1, len(df)):
        delta_h = (df["Data_Hora_Medicao"].iloc[i] - df["Data_Hora_Medicao"].iloc[i-1]).total_seconds() / 3600
        if delta_h > 24:
            gaps.append((df["Data_Hora_Medicao"].iloc[i-1], df["Data_Hora_Medicao"].iloc[i], delta_h))

    print(f"\nGaps > 24h: {len(gaps)}")
    for inicio, fim, h in gaps[:10]:
        print(f"  {inicio} -> {fim} ({h:.0f}h = {h/24:.1f} dias)")

    return df

# Audita todos os CSVs
for f in sorted(DIR.glob("*_consolidado.csv")):
    auditar(f)
