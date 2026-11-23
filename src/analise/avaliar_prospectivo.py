# -*- coding: utf-8 -*-
"""
avaliar_prospectivo.py — Auditoria de integridade e avaliacao pareada da Fase 2
(forecast_runs + forecast_predictions).
Implementa as 3 verificacoes metodologicas:
  1. Agrupamento de blocos adjacentes quando ts_alvo cruza fronteira de bloco;
  2. Distribuicao completa de desvio_alvo_min e sensibilidade (<=5, <=10, <=25 min);
  3. Auditoria de snapshot comum, metadados meteorologicos e contabilizacao de falhas/invalidos.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.relatorios.postgres_db import get_postgres_connection


def _agrupar_blocos_dependentes(df: pd.DataFrame) -> pd.DataFrame:
    """
    Agrupa blocos contiguos de 24h sempre que alguma previsao (ts_origem -> ts_alvo)
    cruzar a fronteira para o bloco seguinte, preservando dependencia temporal no bootstrap.
    """
    df = df.sort_values("ts_origem").copy()
    df["bloco_base"] = df["ts_origem"].dt.floor("24h")
    df["bloco_alvo"] = df["ts_alvo"].dt.floor("24h")

    blocos_unicos = sorted(df["bloco_base"].unique())
    mapa_grupo = {b: b for b in blocos_unicos}

    # Se um bloco tem alvo no bloco seguinte, funde os dois no mesmo cluster
    for _, row in df[df["bloco_alvo"] > df["bloco_base"]].iterrows():
        b_orig = row["bloco_base"]
        b_dest = row["bloco_alvo"]
        if b_dest in mapa_grupo:
            raiz = mapa_grupo[b_orig]
            for k, v in list(mapa_grupo.items()):
                if v == mapa_grupo[b_dest]:
                    mapa_grupo[k] = raiz

    df["cluster_independente"] = df["bloco_base"].map(mapa_grupo)
    return df


def auditar_integridade_fase2() -> None:
    conn = get_postgres_connection()
    try:
        df_runs = pd.read_sql(
            """
            SELECT run_id, ts_origem, cota_origem_cm, regime_observado, snapshot_hash,
                   snapshot_dados->'chuva_bacia'->>'fonte' AS fonte_chuva,
                   (snapshot_dados->'chuva_bacia'->>'idade_arquivo_min')::float AS idade_chuva_min,
                   (snapshot_dados->'erab'->>'idade_min')::float AS idade_erab_min
            FROM forecast_runs
            ORDER BY ts_origem ASC;
            """,
            conn,
        )

        df_pred = pd.read_sql(
            """
            SELECT forecast_id, run_id, model_name, model_version, feature_schema_version,
                   ts_origem, horizonte, ts_alvo, cota_origem_cm,
                   y_pred_delta_cm, y_true_delta_cm, desvio_alvo_min,
                   stale, valido, status_execucao, motivo_falha, features_hash
            FROM forecast_predictions
            ORDER BY ts_origem ASC, model_name, horizonte;
            """,
            conn,
        )
    finally:
        conn.close()

    print(f"=== AUDITORIA DE INTEGRIDADE FASE 2 (Total runs: {len(df_runs)} | Total predictions: {len(df_pred)}) ===")
    if df_pred.empty:
        print("Nenhuma previsao prospectiva registrada ainda.")
        return

    df_pred["ts_origem"] = pd.to_datetime(df_pred["ts_origem"])
    df_pred["ts_alvo"] = pd.to_datetime(df_pred["ts_alvo"])

    # 1. Contabilizacao de validos, stale e falhas por modelo e horizonte
    print("\n--- 1. CONTABILIZACAO DE INTEGRIDADE POR MODELO E HORIZONTE ---")
    resumo_int = (
        df_pred.groupby(["model_name", "model_version", "feature_schema_version", "horizonte"])
        .agg(
            total=("forecast_id", "count"),
            validos=("valido", lambda s: int(s.sum())),
            stale=("stale", lambda s: int(s.sum())),
            falhas=("status_execucao", lambda s: int((s != "OK").sum())),
            com_y_true=("y_true_delta_cm", lambda s: int(s.notna().sum())),
        )
        .reset_index()
    )
    print(resumo_int.to_string(index=False))

    # 2. Auditoria de Snapshot Comum e Metadados Meteorologicos
    print("\n--- 2. SNAPSHOT COMUM E METADADOS DA PREVISAO METEOROLOGICA ---")
    hashes_nulos = int(df_runs["snapshot_hash"].isna().sum())
    idade_chuva_max = df_runs["idade_chuva_min"].max() if not df_runs.empty else None
    idade_erab_max = df_runs["idade_erab_min"].max() if not df_runs.empty else None
    fontes = df_runs["fonte_chuva"].dropna().unique().tolist()
    print(
        f"Runs com snapshot_hash valido: {len(df_runs) - hashes_nulos}/{len(df_runs)} | "
        f"Idade max ERAB: {idade_erab_max:.1f} min | Idade max arquivo chuva: {idade_chuva_max:.1f} min | "
        f"Fontes chuva: {fontes}"
    )

    # 3. Distribuicao de desvio_alvo_min e Sensibilidade (quando houver pares com y_true)
    df_eval = df_pred[df_pred["y_true_delta_cm"].notna() & df_pred["valido"]].copy()
    print(f"\n--- 3. BACKFILL Y_TRUE E SENSIBILIDADE DE JANELA (Pares validos fechados: {len(df_eval)}) ---")
    if df_eval.empty:
        print("Aguardando vencimento dos primeiros ts_alvo (+1h, +3h, +6h) para avaliar desvio_alvo_min.")
        return

    df_eval = _agrupar_blocos_dependentes(df_eval)
    n_clusters = df_eval["cluster_independente"].nunique()
    desv = df_eval["desvio_alvo_min"].dropna()
    print(
        f"Clusters temporais independentes: {n_clusters} | "
        f"Distribuicao desvio_alvo_min: n={len(desv)} | mediana={desv.median():.2f} min | "
        f"p90={np.percentile(desv, 90):.2f} min | max={desv.max():.2f} min"
    )

    for tol in [5.0, 10.0, 25.0]:
        sub_tol = df_eval[df_eval["desvio_alvo_min"] <= tol]
        if sub_tol.empty:
            continue
        print(f"\n  [Tolerancia <= {tol:.0f} min | n={len(sub_tol)}]")
        for (m_name, h), grp in sub_tol.groupby(["model_name", "horizonte"]):
            err = grp["y_pred_delta_cm"] - grp["y_true_delta_cm"]
            print(
                f"    {m_name:16s} | {h} | n={len(grp):3d} | "
                f"MAE={err.abs().mean():.2f} cm | RMSE={(err**2).mean()**0.5:.2f} cm | Vies={err.mean():+.2f} cm"
            )


if __name__ == "__main__":
    auditar_integridade_fase2()
