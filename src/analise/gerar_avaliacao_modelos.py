# -*- coding: utf-8 -*-
"""
gerar_avaliacao_modelos.py — Etapa 3 da Governança Científica ARCTURUS.
Avalia de forma estritamente pareada:
  1. Prospectivo curto (1h, 3h, 6h) em forecast_predictions:
     persistencia vs. v8_final_bacia vs. fisica_3bracos (valido AND NOT stale AND y_true IS NOT NULL).
  2. Modo sombra (logs/sombra_v11c.jsonl) confrontado com a verdade observada da ERAB (leituras):
     - v11c_shadow (24h) vs. persistencia_24h
     - sombra_fisica_3bracos (6h) pareado com v8_final_bacia (6h) e fisica_3bracos (6h)
Salva data/avaliacao_modelos.csv, data/resultado_modelos.parquet e docs/avaliacao_modelos.md.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.relatorios.postgres_db import get_postgres_connection


def avaliar_pareado_curto(conn) -> tuple[pd.DataFrame, list[dict]]:
    df = pd.read_sql(
        """
        SELECT run_id, ts_origem, horizonte, ts_alvo, cota_origem_cm,
               model_name, y_pred_delta_cm, y_true_delta_cm, desvio_alvo_min,
               stale, valido, status_execucao
        FROM forecast_predictions
        WHERE model_name IN ('persistencia', 'v8_final_bacia', 'fisica_3bracos')
          AND status_execucao = 'OK'
          AND valido
          AND NOT stale
          AND y_true_delta_cm IS NOT NULL
          AND y_pred_delta_cm IS NOT NULL
        ORDER BY ts_origem ASC, horizonte, model_name;
        """,
        conn,
    )
    df["ts_origem"] = pd.to_datetime(df["ts_origem"])
    df["ts_alvo"] = pd.to_datetime(df["ts_alvo"])

    piv_pred = df.pivot_table(
        index=["run_id", "ts_origem", "horizonte", "ts_alvo", "cota_origem_cm"],
        columns="model_name",
        values="y_pred_delta_cm",
        aggfunc="first",
    ).reset_index()

    piv_true = (
        df.groupby(["run_id", "horizonte"], as_index=False)["y_true_delta_cm"]
        .first()
    )

    m = pd.merge(piv_pred, piv_true, on=["run_id", "horizonte"], how="inner")
    m = m.dropna(subset=["persistencia", "v8_final_bacia", "fisica_3bracos", "y_true_delta_cm"]).copy()
    m = m.rename(
        columns={
            "persistencia": "previsto_persistencia",
            "v8_final_bacia": "previsto_v8",
            "fisica_3bracos": "previsto_fisica",
            "y_true_delta_cm": "observado",
        }
    )

    m["erro_persistencia"] = m["previsto_persistencia"] - m["observado"]
    m["erro_v8"] = m["previsto_v8"] - m["observado"]
    m["erro_fisica"] = m["previsto_fisica"] - m["observado"]

    resumo = []
    for h in ["1h", "3h", "6h"]:
        sub = m[m["horizonte"] == h]
        if sub.empty:
            continue
        for nome_m, col_e in [
            ("persistencia", "erro_persistencia"),
            ("v8_final_bacia", "erro_v8"),
            ("fisica_3bracos", "erro_fisica"),
        ]:
            err = sub[col_e]
            resumo.append(
                {
                    "grupo_avaliacao": "PROSPECTIVO_CURTO_PAREADO",
                    "horizonte": h,
                    "modelo": nome_m,
                    "n_pares": int(len(sub)),
                    "mae_cm": round(float(err.abs().mean()), 3),
                    "rmse_cm": round(float(np.sqrt((err ** 2).mean())), 3),
                    "vies_cm": round(float(err.mean()), 3),
                    "p90_erro_abs_cm": round(float(np.percentile(err.abs(), 90)), 3),
                }
            )
    return m, resumo


def avaliar_sombra_v11c(conn, df_curto: pd.DataFrame) -> tuple[pd.DataFrame, list[dict]]:
    log_path = Path("logs/sombra_v11c.jsonl")
    if not log_path.exists():
        return pd.DataFrame(), []

    df_erab = pd.read_sql(
        """
        SELECT timestamp, cota_cm
        FROM leituras
        WHERE qc = 'VALIDO' AND cota_cm IS NOT NULL
        ORDER BY timestamp ASC;
        """,
        conn,
    )
    df_erab["ts"] = pd.to_datetime(df_erab["timestamp"])
    df_erab = df_erab[["ts", "cota_cm"]].sort_values("ts").drop_duplicates("ts")

    regs = []
    for line in log_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        ts_o = pd.Timestamp(obj["timestamp"])
        if ts_o.tzinfo is not None:
            ts_o = ts_o.tz_convert("America/Sao_Paulo").tz_localize(None)
        sf = obj.get("sombra_fisica_3bracos") or {}
        regs.append(
            {
                "ts_origem": ts_o,
                "cota_origem_log": obj.get("cota_atual_cm"),
                "delta_v11c_24h": obj.get("delta_pred_24h_cm"),
                "delta_v11c_fis_6h": sf.get("delta_pred_6h_cm"),
                "delta_v11c_fis_12h": sf.get("delta_pred_12h_cm"),
                "confianca": obj.get("confianca_operacional"),
            }
        )

    df_s = pd.DataFrame(regs).sort_values("ts_origem").drop_duplicates("ts_origem")

    # Casar origem causal (backward <= 15 min) e alvo +24h (nearest <= 20 min)
    m_orig = pd.merge_asof(
        df_s,
        df_erab.rename(columns={"ts": "ts_leitura_orig", "cota_cm": "cota_orig_real"}),
        left_on="ts_origem",
        right_on="ts_leitura_orig",
        direction="backward",
        tolerance=pd.Timedelta(minutes=15),
    )
    m_orig["ts_alvo_24h"] = m_orig["ts_origem"] + pd.Timedelta(hours=24)
    m_24 = pd.merge_asof(
        m_orig.sort_values("ts_alvo_24h"),
        df_erab.rename(columns={"ts": "ts_leitura_24h", "cota_cm": "cota_24h_real"}),
        left_on="ts_alvo_24h",
        right_on="ts_leitura_24h",
        direction="nearest",
        tolerance=pd.Timedelta(minutes=20),
    ).sort_values("ts_origem")

    m_24["observado_24h"] = m_24["cota_24h_real"] - m_24["cota_orig_real"]
    valid_24 = m_24.dropna(subset=["delta_v11c_24h", "observado_24h"]).copy()
    valid_24["erro_v11c_24h"] = valid_24["delta_v11c_24h"] - valid_24["observado_24h"]
    valid_24["erro_persistencia_24h"] = 0.0 - valid_24["observado_24h"]

    resumo = []
    if not valid_24.empty:
        for nome_m, col_e in [
            ("persistencia_24h", "erro_persistencia_24h"),
            ("v11c_shadow_24h", "erro_v11c_24h"),
        ]:
            err = valid_24[col_e]
            resumo.append(
                {
                    "grupo_avaliacao": "SOMBRA_24H_PAREADO",
                    "horizonte": "24h",
                    "modelo": nome_m,
                    "n_pares": int(len(valid_24)),
                    "mae_cm": round(float(err.abs().mean()), 3),
                    "rmse_cm": round(float(np.sqrt((err ** 2).mean())), 3),
                    "vies_cm": round(float(err.mean()), 3),
                    "p90_erro_abs_cm": round(float(np.percentile(err.abs(), 90)), 3),
                }
            )

    # Parear ramo 6h do v11c_fisica com v8_final_bacia (6h) quando houver sobreposição temporal (<= 5 min)
    sub_6h = df_curto[df_curto["horizonte"] == "6h"].sort_values("ts_origem").copy()
    sub_v11_6h = m_24.dropna(subset=["delta_v11c_fis_6h"]).sort_values("ts_origem").copy()
    if not sub_6h.empty and not sub_v11_6h.empty:
        p6 = pd.merge_asof(
            sub_6h,
            sub_v11_6h[["ts_origem", "delta_v11c_fis_6h"]].rename(columns={"ts_origem": "ts_v11c"}),
            left_on="ts_origem",
            right_on="ts_v11c",
            direction="nearest",
            tolerance=pd.Timedelta(minutes=5),
        ).dropna(subset=["delta_v11c_fis_6h"])

        if not p6.empty:
            p6["erro_v11c_fis_6h"] = p6["delta_v11c_fis_6h"] - p6["observado"]
            for nome_m, col_e in [
                ("persistencia (subamostra v11c)", "erro_persistencia"),
                ("v8_final_bacia (subamostra v11c)", "erro_v8"),
                ("fisica_3bracos (subamostra v11c)", "erro_fisica"),
                ("v11c_fisica_shadow_6h", "erro_v11c_fis_6h"),
            ]:
                err = p6[col_e]
                resumo.append(
                    {
                        "grupo_avaliacao": "SOMBRA_6H_PAREADO_V8",
                        "horizonte": "6h",
                        "modelo": nome_m,
                        "n_pares": int(len(p6)),
                        "mae_cm": round(float(err.abs().mean()), 3),
                        "rmse_cm": round(float(np.sqrt((err ** 2).mean())), 3),
                        "vies_cm": round(float(err.mean()), 3),
                        "p90_erro_abs_cm": round(float(np.percentile(err.abs(), 90)), 3),
                    }
                )

    return valid_24, resumo




def _metricas_episodios_limiar(df_h: pd.DataFrame, col_pred: str, limiar: float) -> dict:
    """Agrupa cruzamentos em episodios independentes (gap > 6h) e calcula POD, FAR e antecedencia."""
    d = df_h.sort_values("ts_origem").copy()
    d["cota_obs_alvo"] = d["cota_origem_cm"] + d["observado"]
    d["cota_pred_alvo"] = d["cota_origem_cm"] + d[col_pred]
    d["cruzou_real"] = (d["cota_origem_cm"] < limiar) & (d["cota_obs_alvo"] >= limiar)
    d["disparou_pred"] = (d["cota_origem_cm"] < limiar) & (d["cota_pred_alvo"] >= limiar)

    reais = d[d["cruzou_real"]].copy()
    if reais.empty:
        n_ep = 0
    else:
        reais["ep_id"] = (reais["ts_alvo"].diff() > pd.Timedelta(hours=6)).cumsum()
        n_ep = int(reais["ep_id"].nunique())

    detectados = 0
    antecedencias_h = []
    janelas_reais = []
    if n_ep > 0:
        for _, grp in reais.groupby("ep_id"):
            t_ini_cruz = grp["ts_alvo"].min()
            t_fim_cruz = grp["ts_alvo"].max()
            janelas_reais.append((t_ini_cruz - pd.Timedelta(hours=6), t_fim_cruz))
            cand = d[
                d["disparou_pred"]
                & (d["ts_origem"] <= t_ini_cruz)
                & (d["ts_alvo"] >= t_ini_cruz - pd.Timedelta(hours=1))
            ]
            if not cand.empty:
                detectados += 1
                primeiro_alerta = cand["ts_origem"].min()
                ant_h = max(0.0, (t_ini_cruz - primeiro_alerta).total_seconds() / 3600.0)
                antecedencias_h.append(ant_h)

    preds = d[d["disparou_pred"]].copy()
    falsos_alarmes = 0
    if not preds.empty:
        preds["fa_id"] = (preds["ts_origem"].diff() > pd.Timedelta(hours=6)).cumsum()
        for _, grp in preds.groupby("fa_id"):
            t_p0, t_p1 = grp["ts_origem"].min(), grp["ts_alvo"].max()
            bateu_real = any(not (t_p1 < r0 or t_p0 > r1) for r0, r1 in janelas_reais)
            if not bateu_real:
                falsos_alarmes += 1

    pod = round(100.0 * detectados / n_ep, 1) if n_ep > 0 else np.nan
    total_alertas = detectados + falsos_alarmes
    far = round(100.0 * falsos_alarmes / total_alertas, 1) if total_alertas > 0 else 0.0
    ant_med = round(float(np.mean(antecedencias_h)), 2) if antecedencias_h else np.nan
    return {
        "episodios_reais": n_ep,
        "detectados": detectados,
        "pod_pct": pod,
        "falsos_alarmes": falsos_alarmes,
        "far_pct": far,
        "antecedencia_media_h": ant_med,
    }


def avaliar_alertas_por_episodio(conn, df_curto: pd.DataFrame) -> pd.DataFrame:
    linhas = []
    # 1. Serie longa do v8_final_bacia (predicoes_shadow deduplicada por slot de 15 min)
    df_v8 = pd.read_sql(
        """
        SELECT DISTINCT ON (date_trunc('minute', timestamp) - ((extract(minute FROM timestamp)::int % 15) * interval '1 minute'), horizonte)
               timestamp AS ts_origem,
               horizonte,
               cota_atual AS cota_origem_cm,
               y_score AS previsto_v8,
               y_true AS observado
        FROM predicoes_shadow
        WHERE model_version = 'v8_final_bacia'
          AND valido AND NOT stale
          AND y_true IS NOT NULL
          AND cota_atual IS NOT NULL
          AND COALESCE(desvio_alvo_min, 0) <= 10
        ORDER BY date_trunc('minute', timestamp) - ((extract(minute FROM timestamp)::int % 15) * interval '1 minute'),
                 horizonte,
                 COALESCE(ts_predicao, timestamp) DESC;
        """,
        conn,
    )
    if not df_v8.empty:
        df_v8["ts_origem"] = pd.to_datetime(df_v8["ts_origem"])
        horas_map = {"1h": 1, "3h": 3, "6h": 6}
        for h, nh in horas_map.items():
            sub = df_v8[df_v8["horizonte"] == h].copy()
            if sub.empty:
                continue
            sub["ts_alvo"] = sub["ts_origem"] + pd.to_timedelta(nh, unit="h")
            for lim in (150.0, 200.0, 250.0):
                m = _metricas_episodios_limiar(sub, "previsto_v8", lim)
                linhas.append({
                    "serie": "SERIE_LONGA_V8_02NOV_26NOV",
                    "horizonte": h,
                    "modelo": "v8_final_bacia",
                    "limiar_cm": int(lim),
                    **m,
                })

    # 2. Bancada pareada recente (forecast_predictions)
    if not df_curto.empty:
        for h in ("1h", "3h", "6h"):
            sub = df_curto[df_curto["horizonte"] == h].copy()
            if sub.empty:
                continue
            for nome_m, col_p in [
                ("persistencia", "previsto_persistencia"),
                ("v8_final_bacia", "previsto_v8"),
                ("fisica_3bracos", "previsto_fisica"),
            ]:
                for lim in (150.0, 200.0):
                    m = _metricas_episodios_limiar(sub, col_p, lim)
                    linhas.append({
                        "serie": "BANCADA_PAREADA_23NOV_26NOV",
                        "horizonte": h,
                        "modelo": nome_m,
                        "limiar_cm": int(lim),
                        **m,
                    })

    return pd.DataFrame(linhas)


def main() -> None:
    conn = get_postgres_connection()
    try:
        df_curto, res_curto = avaliar_pareado_curto(conn)
        df_24h, res_24h = avaliar_sombra_v11c(conn, df_curto)
        df_alertas = avaliar_alertas_por_episodio(conn, df_curto)
    finally:
        conn.close()

    df_resumo = pd.DataFrame(res_curto + res_24h)

    Path("data").mkdir(exist_ok=True)
    df_resumo.to_csv("data/avaliacao_modelos.csv", index=False)
    df_alertas.to_csv("data/avaliacao_alertas_episodios.csv", index=False)
    df_curto.to_parquet("data/resultado_modelos.parquet", index=False)
    if not df_24h.empty:
        df_24h.to_parquet("data/resultado_modelos_v11c_24h.parquet", index=False)

    print("=== RESUMO COMPARATIVO PAREADO (ETAPA 3) ===")
    print(df_resumo.to_string(index=False))

    # Veredito objetivo por horizonte
    vereditos = []
    for h in ["1h", "3h", "6h"]:
        sub = df_resumo[(df_resumo["grupo_avaliacao"] == "PROSPECTIVO_CURTO_PAREADO") & (df_resumo["horizonte"] == h)]
        if sub.empty:
            continue
        v_mae = sub.loc[sub["mae_cm"].idxmin()]
        v_rmse = sub.loc[sub["rmse_cm"].idxmin()]
        vereditos.append(
            f"- **{h} (`n = {int(v_mae['n_pares'])}` origens pareadas):** "
            f"Menor MAE = **`{v_mae['modelo']}`** (`{v_mae['mae_cm']:.3f} cm`, viés `{v_mae['vies_cm']:+.3f} cm`) | "
            f"Menor RMSE = **`{v_rmse['modelo']}`** (`{v_rmse['rmse_cm']:.3f} cm`)."
        )

    sub24 = df_resumo[df_resumo["grupo_avaliacao"] == "SOMBRA_24H_PAREADO"]
    if not sub24.empty:
        v24 = sub24.loc[sub24["mae_cm"].idxmin()]
        vereditos.append(
            f"- **24h Sombra (`n = {int(v24['n_pares'])}` origens pareadas):** "
            f"Menor MAE = **`{v24['modelo']}`** (`{v24['mae_cm']:.3f} cm`, RMSE `{v24['rmse_cm']:.3f} cm`, viés `{v24['vies_cm']:+.3f} cm`)."
        )

    cols = list(df_resumo.columns)
    md_tab = (
        "| " + " | ".join(cols) + " |\n"
        "| " + " | ".join(["---"] * len(cols)) + " |\n"
        + "\n".join(
            "| " + " | ".join(str(v) for v in row) + " |"
            for row in df_resumo.itertuples(index=False)
        )
    )

    md = "\n".join(
        [
            "# Avaliação Pareada dos Modelos — ARCTURUS CLIMATIK (Etapa 3)",
            "",
            "## Veredito Objetivo por Horizonte (Sem Opinião, Apenas Dados Pareados)",
            "",
            *vereditos,
            "",
            "## Tabela Completa (`data/avaliacao_modelos.csv`)",
            "",
            md_tab,
            "",
            "## Antecipação de Cruzamento de Limiares por Episódio (`data/avaliacao_alertas_episodios.csv`)",
            "",
            "| " + " | ".join(df_alertas.columns) + " |",
            "| " + " | ".join(["---"] * len(df_alertas.columns)) + " |",
            *[
                "| " + " | ".join(str(v) for v in row) + " |"
                for row in df_alertas.itertuples(index=False)
            ],
            "",
        ]
    )
    Path("docs/avaliacao_modelos.md").write_text(md, encoding="utf-8")

    print("\n=== VEREDITO OBJETIVO POR HORIZONTE ===")
    for linha in vereditos:
        print(linha)
    print("\n[OK] Salvo em data/avaliacao_modelos.csv, data/resultado_modelos.parquet e docs/avaliacao_modelos.md")


if __name__ == "__main__":
    main()
