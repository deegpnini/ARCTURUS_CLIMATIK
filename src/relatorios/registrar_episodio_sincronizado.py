#!/usr/bin/env python3
"""
Registra, para um mesmo instante/ciclo de referência:
- cotas e horários válidos da ERAB (PostgreSQL: leituras)
- chuva observada por estação (Defesa Civil SC + grade complementar, <= ts_ref)
- previsão meteorológica disponível no ciclo (<= ts_ref)
- previsões por modelo disponíveis (forecast_predictions / sombra_v11c.jsonl, <= ts_ref)
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
import pandas as pd

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.relatorios.postgres_db import get_postgres_connection

OUT_JSONL = BASE / "data" / "auditoria_sincronizada_episodio.jsonl"


def _normalizar_ts(val) -> pd.Timestamp | None:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    ts = pd.Timestamp(val)
    if ts.tzinfo is not None:
        ts = ts.tz_convert("America/Sao_Paulo").tz_localize(None)
    return ts


def ler_erab(conn, ts_ref: pd.Timestamp, limite: int = 20) -> list[dict]:
    sql = """
        SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, regime, chuva_pior_caso_mm, qc
        FROM leituras
        WHERE qc = 'VALIDO'
          AND timestamp <= %s
        ORDER BY timestamp DESC
        LIMIT %s;
    """
    df = pd.read_sql(sql, conn, params=(ts_ref.to_pydatetime(), limite))
    if df.empty:
        return []
    df["timestamp"] = df["timestamp"].astype(str)
    return df.to_dict(orient="records")


def ler_chuva_dcsc(ts_ref: pd.Timestamp) -> dict:
    hist_path = BASE / "data" / "historico_defesacivil_bacia.jsonl"
    snap_path = BASE / "data" / "chuva_defesacivil_realtime.json"
    registros = []

    if hist_path.exists():
        for linha in hist_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not linha.strip():
                continue
            try:
                obj = json.loads(linha)
                ts_c = _normalizar_ts(obj.get("timestamp_coleta") or obj.get("timestamp"))
                if ts_c is not None and ts_c <= ts_ref:
                    registros.append((ts_c, obj))
            except Exception:
                continue

    if not registros and snap_path.exists():
        try:
            obj = json.loads(snap_path.read_text(encoding="utf-8"))
            ts_c = _normalizar_ts(obj.get("timestamp_coleta") or obj.get("timestamp"))
            if ts_c is not None and ts_c <= ts_ref:
                registros.append((ts_c, obj))
        except Exception:
            pass

    if not registros:
        return {"ts_coleta": None, "estacoes": []}

    registros.sort(key=lambda item: item[0])
    ts_ult, ult_obj = registros[-1]
    estacoes_limpas = []
    for est in ult_obj.get("estacoes", []):
        estacoes_limpas.append({
            "codigo": est.get("codigo"),
            "nome": est.get("nome_oficial") or est.get("nome") or est.get("estacao"),
            "trecho_bacia": est.get("trecho_bacia"),
            "atualizacao_estacao": est.get("atualizacao_estacao"),
            "chuva_1h_mm": est.get("chuva_1h_mm"),
            "chuva_6h_mm": est.get("chuva_6h_mm"),
            "chuva_12h_mm": est.get("chuva_12h_mm"),
            "chuva_24h_mm": est.get("chuva_24h_mm"),
            "chuva_48h_mm": est.get("chuva_48h_mm"),
            "chuva_72h_mm": est.get("chuva_72h_mm"),
            "rio_m": est.get("rio_m"),
        })

    return {
        "ts_coleta": ts_ult.isoformat(timespec="seconds"),
        "estacoes": estacoes_limpas,
    }


def ler_grade_chuva(ts_ref: pd.Timestamp) -> dict:
    csv_path = BASE / "data" / "chuva_bacia_openmeteo.csv"
    if not csv_path.exists():
        return {"disponivel": False, "linhas_ate_ts_ref": 0, "acumulado_24h_media_mm": None}

    df = pd.read_csv(csv_path, index_col=0, parse_dates=True)
    if df.empty:
        return {"disponivel": False, "linhas_ate_ts_ref": 0, "acumulado_24h_media_mm": None}

    df.index = pd.to_datetime(df.index, errors="coerce")
    df = df.loc[~df.index.isna()].sort_index()
    df_ate = df[df.index <= ts_ref]
    if df_ate.empty:
        return {"disponivel": False, "linhas_ate_ts_ref": 0, "acumulado_24h_media_mm": None}

    corte_24h = ts_ref - pd.Timedelta(hours=24)
    jan_24h = df_ate[df_ate.index > corte_24h]
    cols_num = df_ate.select_dtypes(include="number").columns
    acum_24h = round(float(jan_24h[cols_num].mean(axis=1).sum()), 3) if not jan_24h.empty and len(cols_num) > 0 else None

    return {
        "disponivel": True,
        "ultimo_ts_grade": str(df_ate.index.max()),
        "linhas_ate_ts_ref": int(len(df_ate)),
        "acumulado_24h_media_mm": acum_24h,
    }


def ler_previsao_meteorologica_ciclo(ts_ref: pd.Timestamp) -> dict:
    meta_path = BASE / "data" / "previsao_tempo_meta.json"
    json_path = BASE / "data" / "previsao_tempo.json"
    meta = {}
    if meta_path.exists():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except Exception:
            meta = {}

    if not json_path.exists():
        return {"disponivel": False, "meta": meta, "dados_cidades": {}}

    try:
        raw = json.loads(json_path.read_text(encoding="utf-8"))
    except Exception:
        return {"disponivel": False, "meta": meta, "dados_cidades": {}}

    return {
        "disponivel": True,
        "meta": meta,
        "dados_cidades": raw if isinstance(raw, dict) else {},
    }


def ler_previsoes_modelos(conn, ts_ref: pd.Timestamp) -> dict:
    sombra_path = BASE / "logs" / "sombra_v11c.jsonl"
    sombra_linhas = []
    if sombra_path.exists():
        for linha in sombra_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            if not linha.strip():
                continue
            try:
                obj = json.loads(linha)
                ts_s = _normalizar_ts(obj.get("timestamp") or obj.get("ts_origem"))
                if ts_s is not None and ts_s <= ts_ref:
                    sombra_linhas.append(obj)
            except Exception:
                continue

    pg_preds = []
    try:
        sql = """
            SELECT run_id, model_name, model_version, feature_schema_version,
                   ts_origem, horizonte, ts_alvo, cota_origem_cm,
                   y_pred_delta_cm, stale, valido, status_execucao
            FROM forecast_predictions
            WHERE ts_origem <= %s
            ORDER BY ts_origem DESC, forecast_id DESC
            LIMIT 18;
        """
        df_p = pd.read_sql(sql, conn, params=(ts_ref.to_pydatetime(),))
        if not df_p.empty:
            for col in ["ts_origem", "ts_alvo"]:
                df_p[col] = df_p[col].astype(str)
            pg_preds = df_p.to_dict(orient="records")
    except Exception:
        pg_preds = []

    return {
        "ultima_sombra_v11c": sombra_linhas[-1] if sombra_linhas else None,
        "ultimas_forecast_predictions": pg_preds,
    }


def main():
    parser = argparse.ArgumentParser(description="Registra snapshot sincronizado de episódio sem previsão futura vazada.")
    parser.add_argument("--ts-ref", type=str, default=None, help="Timestamp de referência (ex: '2026-11-24 13:55:00'). Padrão: agora.")
    parser.add_argument("--nota", type=str, default="", help="Observação contextual do ciclo.")
    args = parser.parse_args()

    ts_ref = _normalizar_ts(args.ts_ref) if args.ts_ref else pd.Timestamp(datetime.now()).floor("s")

    conn = get_postgres_connection()
    try:
        erab_rows = ler_erab(conn, ts_ref=ts_ref, limite=20)
        modelos = ler_previsoes_modelos(conn, ts_ref=ts_ref)
    finally:
        conn.close()

    registro = {
        "ts_registro": datetime.now().isoformat(timespec="seconds"),
        "ts_referencia_ciclo": ts_ref.isoformat(timespec="seconds"),
        "nota": args.nota,
        "erab_leituras_validas": erab_rows,
        "chuva_observada_dcsc": ler_chuva_dcsc(ts_ref=ts_ref),
        "chuva_grade_complementar": ler_grade_chuva(ts_ref=ts_ref),
        "previsao_meteorologica_ciclo": ler_previsao_meteorologica_ciclo(ts_ref=ts_ref),
        "previsoes_modelos": modelos,
    }

    OUT_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSONL, "a", encoding="utf-8") as f:
        f.write(json.dumps(registro, ensure_ascii=False) + "\n")

    print(f"[OK] Snapshot gravado em {OUT_JSONL} | ts_referencia={registro['ts_referencia_ciclo']}")
    print(f"     ERAB leituras válidas <= ts_ref: {len(erab_rows)}")
    print(f"     Estações DCSC <= ts_ref: {len(registro['chuva_observada_dcsc']['estacoes'])} (coleta: {registro['chuva_observada_dcsc']['ts_coleta']})")
    print(f"     Grade chuva 24h média <= ts_ref: {registro['chuva_grade_complementar']['acumulado_24h_media_mm']}")


if __name__ == "__main__":
    main()
