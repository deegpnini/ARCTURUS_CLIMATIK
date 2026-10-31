import pandas as pd
import numpy as np
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[2]
ARQUIVO_BACIA = BASE_DIR / "data" / "chuva_bacia_openmeteo.csv"

def calcular_features_bacia(data_alvo):
    features_vazias = {
        "bacia_lag_4h": 0.0,
        "bacia_3h": 0.0,
        "bacia_pontos_forte": 0.0
    }

    if not ARQUIVO_BACIA.exists():
        return features_vazias

    try:
        df = pd.read_csv(ARQUIVO_BACIA, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df.loc[~df.index.isna()].sort_index()
        if df.empty:
            return features_vazias

        df_ate_alvo = df[df.index <= data_alvo]

        if df_ate_alvo.empty:
            return features_vazias

        cols_chuva = df.select_dtypes(include=[np.number]).columns
        if len(cols_chuva) == 0:
            return features_vazias

        chuva_media = df_ate_alvo[cols_chuva].mean(axis=1)

        bacia_lag_4h = chuva_media.shift(4).iloc[-1] if len(chuva_media) >= 4 else 0.0
        bacia_3h = chuva_media.rolling(window=3).sum().iloc[-1] if len(chuva_media) >= 3 else chuva_media.sum()

        ultima_leitura = df_ate_alvo[cols_chuva].iloc[-1]
        bacia_pontos_forte = (ultima_leitura > 5.0).sum()

        return {
            "bacia_lag_4h": float(bacia_lag_4h) if not pd.isna(bacia_lag_4h) else 0.0,
            "bacia_3h": float(bacia_3h) if not pd.isna(bacia_3h) else 0.0,
            "bacia_pontos_forte": float(bacia_pontos_forte) if not pd.isna(bacia_pontos_forte) else 0.0
        }
    except Exception as e:
        print(f"[AVISO] Falha ao processar features de bacia: {e}")
        return features_vazias
