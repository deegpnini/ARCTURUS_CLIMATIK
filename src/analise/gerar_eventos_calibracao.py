# -*- coding: utf-8 -*-
"""
gerar_eventos_calibracao.py — Etapa 2 da Governança Científica ARCTURUS.
Consolida eventos hidrológicos reais segmentados na série da régua ERAB (leituras)
e cruza com pluviometria observada (historico_defesacivil_bacia.jsonl),
histórico diário validado (ana_historico) e metadados de lag (lag_eventos.jsonl).
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

CODIGOS_CABECEIRA = {"DCSC-00054", "DCSC-00046", "DCSC-00151"}  # Lauro Muller, Orleans, Grao-Para
CODIGOS_MEDIO_CURSO = {"DCSC-00122"}  # Sao Ludgero
CODIGOS_BACIA = CODIGOS_CABECEIRA | CODIGOS_MEDIO_CURSO | {"DCSC-00048"}  # + Tubarao/Guarda


def carregar_erab(conn) -> pd.DataFrame:
    df = pd.read_sql(
        """
        SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, regime, chuva_pior_caso_mm
        FROM leituras
        WHERE qc = 'VALIDO' AND cota_cm IS NOT NULL
        ORDER BY timestamp ASC;
        """,
        conn,
    )
    df["ts"] = pd.to_datetime(df["timestamp"])
    return df


def carregar_dcsc() -> pd.DataFrame:
    path = Path("data/historico_defesacivil_bacia.jsonl")
    if not path.exists():
        return pd.DataFrame()
    rows = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        reg = json.loads(line)
        ts_c = pd.Timestamp(reg.get("timestamp_coleta") or reg.get("timestamp"))
        if ts_c.tzinfo is not None:
            ts_c = ts_c.tz_convert("America/Sao_Paulo").tz_localize(None)
        for est in reg.get("estacoes", []):
            rows.append(
                {
                    "ts": ts_c,
                    "codigo": (est.get("codigo") or "").strip(),
                    "trecho": (est.get("trecho_bacia") or est.get("nome_oficial") or "").strip(),
                    "chuva_1h": est.get("chuva_1h_mm"),
                    "chuva_6h": est.get("chuva_6h_mm"),
                    "chuva_24h": est.get("chuva_24h_mm"),
                }
            )
    if not rows:
        return pd.DataFrame()
    return pd.DataFrame(rows).sort_values("ts")


def segmentar_episodios_erab(df_erab: pd.DataFrame) -> list[dict]:
    """
    Segmenta episódios de cheia/repique na série da ERAB:
    - Reamostra em grade regular de 15 min (sem interpolar lacunas > 45 min)
    - Início: elevação >= 12 cm em 3h ou >= 15 cm acima da base recente
    - Pico: máximo local do episódio
    - Fim: retorno a <= base + 12 cm ou queda >= 65% da amplitude com >= 6h de recessão
    """
    s = df_erab.set_index("ts")["cota_cm"].resample("15min").median()
    s_interp = s.interpolate(method="time", limit=3)

    episodios = []
    em_evento = False
    ep = {}

    vals = s_interp.values
    idx = s_interp.index

    for i in range(12, len(vals)):
        c_atual = vals[i]
        if np.isnan(c_atual):
            continue

        janela_3h = vals[max(0, i - 12) : i + 1]
        janela_6h = vals[max(0, i - 24) : i + 1]
        if np.all(np.isnan(janela_3h)):
            continue

        base_3h = float(np.nanmin(janela_3h))
        base_6h = float(np.nanmin(janela_6h))

        if not em_evento:
            if (c_atual - base_3h) >= 12.0 or (c_atual - base_6h) >= 18.0:
                idx_base = max(0, i - 24) + int(np.nanargmin(janela_6h))
                # Encontra primeiro instante de subida >= 3 cm após a base
                ts_subida = idx[i]
                for j in range(idx_base + 1, i + 1):
                    if not np.isnan(vals[j]) and (vals[j] - base_6h) >= 3.0:
                        ts_subida = idx[j]
                        break

                em_evento = True
                ep = {
                    "ts_inicio": idx[idx_base],
                    "ts_subida": ts_subida,
                    "cota_base": round(base_6h, 2),
                    "cota_pico": round(float(c_atual), 2),
                    "ts_pico": idx[i],
                }
        else:
            if c_atual >= ep["cota_pico"]:
                ep["cota_pico"] = round(float(c_atual), 2)
                ep["ts_pico"] = idx[i]

            delta_pico = ep["cota_pico"] - ep["cota_base"]
            horas_pos_pico = (idx[i] - ep["ts_pico"]).total_seconds() / 3600.0
            recuo_relativo = (ep["cota_pico"] - c_atual) / max(delta_pico, 1.0)

            # Verifica se há um novo repique forte antes de fechar
            if horas_pos_pico >= 6.0 and (
                c_atual <= ep["cota_base"] + 12.0 or recuo_relativo >= 0.65
            ):
                ep["ts_fim"] = idx[i]
                ep["cota_fim"] = round(float(c_atual), 2)
                episodios.append(ep)
                em_evento = False
                ep = {}

    if em_evento and ep:
        ultimo_valid = s_interp.dropna()
        ep["ts_fim"] = ultimo_valid.index[-1]
        ep["cota_fim"] = round(float(ultimo_valid.iloc[-1]), 2)
        episodios.append(ep)

    return episodios


def resumir_chuva_episodio(df_dcsc: pd.DataFrame, ts_inicio: pd.Timestamp, ts_pico: pd.Timestamp) -> dict:
    if df_dcsc.empty:
        return {
            "fonte_chuva": "SEM_DCSC_NA_JANELA",
            "dominante_24h": None,
            "chuva_max_24h": None,
            "dominante_6h": None,
            "chuva_max_6h": None,
            "chuva_media_bacia": None,
            "chuva_cabeceira": None,
            "chuva_medio_curso": None,
        }

    jan = df_dcsc[
        (df_dcsc["ts"] >= ts_inicio - pd.Timedelta(hours=6))
        & (df_dcsc["ts"] <= ts_pico + pd.Timedelta(hours=1))
    ].copy()

    if jan.empty:
        return {
            "fonte_chuva": "SEM_DCSC_NA_JANELA",
            "dominante_24h": None,
            "chuva_max_24h": None,
            "dominante_6h": None,
            "chuva_max_6h": None,
            "chuva_media_bacia": None,
            "chuva_cabeceira": None,
            "chuva_medio_curso": None,
        }

    max_por_est_24 = jan.dropna(subset=["chuva_24h"]).groupby(["codigo", "trecho"])["chuva_24h"].max().reset_index()
    max_por_est_6 = jan.dropna(subset=["chuva_6h"]).groupby(["codigo", "trecho"])["chuva_6h"].max().reset_index()

    dom_24, max_24 = None, None
    if not max_por_est_24.empty:
        r24 = max_por_est_24.loc[max_por_est_24["chuva_24h"].idxmax()]
        dom_24 = r24["trecho"]
        max_24 = round(float(r24["chuva_24h"]), 2)

    dom_6, max_6 = None, None
    if not max_por_est_6.empty:
        r6 = max_por_est_6.loc[max_por_est_6["chuva_6h"].idxmax()]
        dom_6 = r6["trecho"]
        max_6 = round(float(r6["chuva_6h"]), 2)

    bacia_vals = max_por_est_24[max_por_est_24["codigo"].isin(CODIGOS_BACIA)]["chuva_24h"]
    cab_vals = max_por_est_24[max_por_est_24["codigo"].isin(CODIGOS_CABECEIRA)]["chuva_24h"]
    med_vals = max_por_est_24[max_por_est_24["codigo"].isin(CODIGOS_MEDIO_CURSO)]["chuva_24h"]

    return {
        "fonte_chuva": "DEFESA_CIVIL_SC",
        "dominante_24h": dom_24,
        "chuva_max_24h": max_24,
        "dominante_6h": dom_6,
        "chuva_max_6h": max_6,
        "chuva_media_bacia": round(float(bacia_vals.mean()), 2) if not bacia_vals.empty else None,
        "chuva_cabeceira": round(float(cab_vals.mean()), 2) if not cab_vals.empty else None,
        "chuva_medio_curso": round(float(med_vals.mean()), 2) if not med_vals.empty else None,
    }


def main() -> None:
    conn = get_postgres_connection()
    try:
        df_erab = carregar_erab(conn)
        df_ana = pd.read_sql("SELECT timestamp, cota_cm FROM ana_historico ORDER BY timestamp ASC;", conn)
    finally:
        conn.close()

    df_dcsc = carregar_dcsc()
    episodios_raw = segmentar_episodios_erab(df_erab)

    # Referência climatológica validada (ana_historico)
    p50_ana = float(df_ana["cota_cm"].median()) if not df_ana.empty else 41.25
    p90_ana = float(df_ana["cota_cm"].quantile(0.90)) if not df_ana.empty else 133.45

    # Metadados auxiliares de lag_eventos.jsonl e evento_atual_bacia.json
    lag_ref = {}
    p_lag = Path("data/lag_eventos.jsonl")
    if p_lag.exists():
        for ln in p_lag.read_text(encoding="utf-8").splitlines():
            if ln.strip():
                obj = json.loads(ln)
                lag_ref[str(obj.get("evento"))] = obj

    registros = []
    for idx_ep, ep in enumerate(episodios_raw, start=1):
        ts_ini = ep["ts_inicio"]
        ts_sub = ep["ts_subida"]
        ts_pic = ep["ts_pico"]
        ts_fim = ep["ts_fim"]

        delta_total = round(ep["cota_pico"] - ep["cota_base"], 2)
        tempo_ate_subida = round(max((ts_sub - ts_ini).total_seconds() / 3600.0, 0.0), 2)
        tempo_ate_pico = round(max((ts_pic - ts_ini).total_seconds() / 3600.0, 0.0), 2)
        duracao_total_h = round(max((ts_fim - ts_ini).total_seconds() / 3600.0, 0.0), 2)

        sub_erab = df_erab[(df_erab["ts"] >= ts_ini) & (df_erab["ts"] <= ts_fim)]
        vz_max = round(float(sub_erab["vz_cm_h"].max()), 2) if not sub_erab.empty and sub_erab["vz_cm_h"].notna().any() else None

        chuva_info = resumir_chuva_episodio(df_dcsc, ts_ini, ts_pic)
        evento_id = f"EP{idx_ep:02d}_{ts_ini.strftime('%Y%m%d_%H%M')}"

        if ep["cota_pico"] >= 350.0:
            classe_severidade = "ATENCAO_CRITICA (>=350cm)"
        elif ep["cota_pico"] >= 220.0:
            classe_severidade = "CHEIA_MODERADA (220-349cm)"
        elif ep["cota_pico"] >= p90_ana:
            classe_severidade = f"ELEVACAO_ACIMA_P90 (>{p90_ana:.0f}cm)"
        else:
            classe_severidade = "PULSO_INTERNO"

        registros.append(
            {
                "evento": evento_id,
                "ts_inicio": ts_ini.strftime("%Y-%m-%d %H:%M:%S"),
                "ts_subida": ts_sub.strftime("%Y-%m-%d %H:%M:%S"),
                "ts_pico": ts_pic.strftime("%Y-%m-%d %H:%M:%S"),
                "ts_fim": ts_fim.strftime("%Y-%m-%d %H:%M:%S"),
                "dominante_24h": chuva_info["dominante_24h"],
                "dominante_6h": chuva_info["dominante_6h"],
                "chuva_max_24h": chuva_info["chuva_max_24h"],
                "chuva_max_6h": chuva_info["chuva_max_6h"],
                "chuva_media_bacia": chuva_info["chuva_media_bacia"],
                "chuva_cabeceira": chuva_info["chuva_cabeceira"],
                "chuva_medio_curso": chuva_info["chuva_medio_curso"],
                "fonte_chuva": chuva_info["fonte_chuva"],
                "cota_base": ep["cota_base"],
                "cota_pico": ep["cota_pico"],
                "cota_fim": ep["cota_fim"],
                "delta_total": delta_total,
                "tempo_ate_subida": tempo_ate_subida,
                "tempo_ate_pico": tempo_ate_pico,
                "duracao_total_h": duracao_total_h,
                "vz_max_cm_h": vz_max,
                "classe_severidade": classe_severidade,
                "ref_ana_p50_cm": round(p50_ana, 2),
                "ref_ana_p90_cm": round(p90_ana, 2),
                "lag_jsonl_ref": ",".join(lag_ref.keys()) if lag_ref else None,
            }
        )

    df_out = pd.DataFrame(registros)

    # Salvar CSV e Parquet
    Path("data").mkdir(exist_ok=True)
    df_out.to_csv("data/eventos_calibracao.csv", index=False)
    df_out.to_parquet("data/eventos_calibracao.parquet", index=False)

    # Gravar tabela eventos_calibracao no PostgreSQL
    conn = get_postgres_connection()
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS eventos_calibracao;")
    cur.execute(
        """
        CREATE TABLE eventos_calibracao (
            evento TEXT PRIMARY KEY,
            ts_inicio TIMESTAMP NOT NULL,
            ts_subida TIMESTAMP,
            ts_pico TIMESTAMP NOT NULL,
            ts_fim TIMESTAMP,
            dominante_24h TEXT,
            dominante_6h TEXT,
            chuva_max_24h DOUBLE PRECISION,
            chuva_max_6h DOUBLE PRECISION,
            chuva_media_bacia DOUBLE PRECISION,
            chuva_cabeceira DOUBLE PRECISION,
            chuva_medio_curso DOUBLE PRECISION,
            fonte_chuva TEXT,
            cota_base DOUBLE PRECISION,
            cota_pico DOUBLE PRECISION,
            cota_fim DOUBLE PRECISION,
            delta_total DOUBLE PRECISION,
            tempo_ate_subida DOUBLE PRECISION,
            tempo_ate_pico DOUBLE PRECISION,
            duracao_total_h DOUBLE PRECISION,
            vz_max_cm_h DOUBLE PRECISION,
            classe_severidade TEXT,
            ref_ana_p50_cm DOUBLE PRECISION,
            ref_ana_p90_cm DOUBLE PRECISION,
            lag_jsonl_ref TEXT
        );
        """
    )

    cols = list(df_out.columns)
    placeholders = ", ".join(["%s"] * len(cols))
    sql_ins = f"INSERT INTO eventos_calibracao ({', '.join(cols)}) VALUES ({placeholders});"
    for _, row in df_out.iterrows():
        vals = [None if pd.isna(v) else (v.item() if hasattr(v, "item") else v) for v in row]
        cur.execute(sql_ins, vals)

    conn.commit()
    cur.close()
    conn.close()

    # Gerar resumo Markdown
    cols_show = [
        "evento",
        "dominante_24h",
        "dominante_6h",
        "chuva_max_24h",
        "chuva_media_bacia",
        "cota_base",
        "cota_pico",
        "delta_total",
        "tempo_ate_subida",
        "tempo_ate_pico",
        "classe_severidade",
    ]
    print(f"=== TABELA eventos_calibracao GERADA ({len(df_out)} episódios) ===")
    print(df_out[cols_show].to_string(index=False))

    md_lines = [
        "# Tabela Científica de Calibração de Eventos — ARCTURUS CLIMATIK",
        "",
        f"- **Total de episódios segmentados (ERAB):** `{len(df_out)}`",
        f"- **Referência climatológica ANA 84580000 (`ana_historico`):** `P50 = {p50_ana:.2f} cm` | `P90 = {p90_ana:.2f} cm`",
        "- **Artefatos gerados:** `PostgreSQL -> eventos_calibracao`, `data/eventos_calibracao.csv`, `data/eventos_calibracao.parquet`",
        "",
        "## Resumo dos Episódios",
        "",
        "| " + " | ".join(cols_show) + " |\n" + "| " + " | ".join(["---"] * len(cols_show)) + " |\n" + "\n".join("| " + " | ".join("" if v is None or (isinstance(v, float) and v != v) else str(v) for v in row) + " |" for row in df_out[cols_show].itertuples(index=False)),
        "",
    ]
    Path("docs/eventos_calibracao.md").write_text("\n".join(md_lines), encoding="utf-8")
    print("\n[OK] Salvo em PostgreSQL (eventos_calibracao), data/eventos_calibracao.csv, data/eventos_calibracao.parquet e docs/eventos_calibracao.md")


if __name__ == "__main__":
    main()
