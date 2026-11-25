# -*- coding: utf-8 -*-
"""
executar_rodada_prospectiva.py — Coleta prospectiva pareada (forecast_runs + forecast_predictions).
Garante origem compartilhada imutavel (snapshot_dados + snapshot_hash) e avalia lado a lado:
  1. persistencia (v1.0)
  2. v8_final_bacia (v8_final_bacia)
  3. fisica_3bracos (v1.0, feature_schema_version='fisica_v1.0', parametros congelados a priori)
Tambem realiza o backfill automatico de y_true_delta_cm para previsoes cujo ts_alvo ja venceu.
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import sys
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_ROOT = str(Path(__file__).resolve().parents[2])
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src.relatorios.postgres_db import get_postgres_connection

BASE_DIR = Path(__file__).resolve().parents[2]
RAIN_CSV = BASE_DIR / "data" / "chuva_bacia_openmeteo.csv"
DCSC_HIST = BASE_DIR / "data" / "historico_defesacivil_bacia.jsonl"
LOG_FILE = BASE_DIR / "logs" / "prospectivo.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
LOGGER = logging.getLogger("prospectivo")

COLS_OESTE = ["lauro_muller", "orleans", "pedras_grandes"]
COLS_NORTE = ["braco_norte", "sao_ludgero", "grao_para", "rio_fortuna"]
COLS_LESTE = ["pouso"]

HORIZONTES = {"1h": 1, "3h": 3, "6h": 6}

# Parametros fisicos congelados a priori (fisica_v1.0 — zero recalibracao no periodo prospectivo)
# Coeficientes de resposta linearizada (cm de variacao de cota por mm de chuva efetiva ou cm/h de inercia)
PARAMS_FISICA_V1 = {
    "1h": {"k_vz": 0.45, "tau_vz": 1.0, "c_estado": 0.35, "c_oeste": 0.10, "c_norte": 0.12, "c_leste": 0.15, "c_jusante": 0.0},
    "3h": {"k_vz": 0.95, "tau_vz": 2.2, "c_estado": 0.85, "c_oeste": 0.35, "c_norte": 0.45, "c_leste": 0.30, "c_jusante": 0.0},
    "6h": {"k_vz": 1.25, "tau_vz": 3.0, "c_estado": 1.35, "c_oeste": 0.85, "c_norte": 0.95, "c_leste": 0.45, "c_jusante": 0.0},
}


def _sha256_obj(obj) -> str:
    raw = json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _limpar_nan(obj):
    if isinstance(obj, dict):
        return {k: _limpar_nan(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_limpar_nan(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    return obj


def _coletar_snapshot_unificado(conn) -> dict:
    """Constroi o snapshot imutavel disponivel exatamente no momento ts_origem."""
    ts_origem = pd.Timestamp.now()
    cur = conn.cursor()

    # 1. Leitura valida mais recente da ERAB
    cur.execute(
        """
        SELECT timestamp, cota_cm, vz_cm_h, az_cm_h2, regime, chuva_pior_caso_mm
        FROM leituras
        WHERE qc = 'VALIDO' AND cota_cm IS NOT NULL
        ORDER BY timestamp DESC
        LIMIT 1;
        """
    )
    row_erab = cur.fetchone()
    if not row_erab:
        raise RuntimeError("Nenhuma leitura VALIDO encontrada na tabela leituras.")

    ts_erab = pd.Timestamp(row_erab[0])
    cota_origem = float(row_erab[1])
    vz_atual = float(row_erab[2]) if row_erab[2] is not None else 0.0
    az_atual = float(row_erab[3]) if row_erab[3] is not None else 0.0
    regime_obs = str(row_erab[4]) if row_erab[4] is not None else "NORMAL"
    idade_erab_min = round((ts_origem - ts_erab).total_seconds() / 60.0, 2)

    # 2. Previsoes atuais do v8_final_bacia geradas neste ciclo (se disponiveis e frescas <= 20 min)
    cur.execute(
        """
        SELECT COALESCE(ts_predicao, timestamp) AS ts_p, horizonte, y_score, stale, valido, features_hash
        FROM predicoes_shadow
        WHERE model_version = 'v8_final_bacia'
          AND COALESCE(ts_predicao, timestamp) >= %s::timestamp - INTERVAL '20 minutes'
        ORDER BY COALESCE(ts_predicao, timestamp) DESC;
        """,
        (ts_origem.strftime("%Y-%m-%d %H:%M:%S"),),
    )
    v8_rows = {}
    for ts_p, h, y_sc, st, val, f_hash in cur.fetchall():
        if h not in v8_rows:
            v8_rows[h] = {
                "ts_predicao": pd.Timestamp(ts_p).isoformat(),
                "y_pred_delta_cm": float(y_sc) if y_sc is not None else None,
                "stale": bool(st),
                "valido": bool(val),
                "features_hash": f_hash,
            }

    # 3. Contorno de jusante (Laguna) com timestamp <= ts_origem
    cur.execute(
        """
        SELECT timestamp, mare_msl_m, componente_sul_kmh, risco_remanso
        FROM contorno_jusante
        WHERE timestamp <= %s::timestamp
          AND timestamp >= %s::timestamp - INTERVAL '12 hours'
        ORDER BY timestamp ASC;
        """,
        (ts_origem.strftime("%Y-%m-%d %H:%M:%S"), ts_origem.strftime("%Y-%m-%d %H:%M:%S")),
    )
    rows_jus = cur.fetchall()
    cur.close()

    jusante = {
        "disponivel": bool(rows_jus),
        "mare_msl_m": None,
        "mare_anomalia_m": None,
        "mare_delta_3h_m": None,
        "componente_sul_kmh": None,
        "risco_remanso": None,
        "ts_jusante": None,
    }
    if rows_jus:
        df_j = pd.DataFrame(rows_jus, columns=["ts", "mare", "vsul", "risco"])
        mare_now = float(df_j["mare"].iloc[-1])
        mare_3h = float(df_j["mare"].iloc[-4]) if len(df_j) >= 4 else float(df_j["mare"].iloc[0])
        jusante.update({
            "mare_msl_m": round(mare_now, 4),
            "mare_anomalia_m": round(mare_now - 0.0, 4),  # Referencia MSL local = 0.00 m
            "mare_delta_3h_m": round(mare_now - mare_3h, 4),
            "componente_sul_kmh": round(float(df_j["vsul"].iloc[-1]), 2),
            "risco_remanso": str(df_j["risco"].iloc[-1]),
            "ts_jusante": pd.Timestamp(df_j["ts"].iloc[-1]).isoformat(),
        })

    # 4. Chuva observada + previsao horaria arquivada em data/chuva_bacia_openmeteo.csv
    chuva_meta = {
        "fonte": "Open-Meteo Forecast/Archive (chuva_bacia_openmeteo.csv)",
        "unidades": "mm/h",
        "ponderacao_espacial": "media_aritmetica_estacoes_ramo",
        "arquivo_existe": RAIN_CSV.exists(),
        "idade_arquivo_min": None,
        "stale_chuva": True,
        "obs_oeste_lag_8_12h_mm": 0.0,
        "obs_norte_lag_5_8h_mm": 0.0,
        "obs_leste_lag_4_6h_mm": 0.0,
        "obs_bacia_6h_mm": 0.0,
        "prev_oeste_mm": {"1h": 0.0, "3h": 0.0, "6h": 0.0},
        "prev_norte_mm": {"1h": 0.0, "3h": 0.0, "6h": 0.0},
        "prev_leste_mm": {"1h": 0.0, "3h": 0.0, "6h": 0.0},
    }

    if RAIN_CSV.exists():
        mtime = datetime.fromtimestamp(RAIN_CSV.stat().st_mtime)
        idade_min = round((ts_origem.to_pydatetime() - mtime).total_seconds() / 60.0, 2)
        chuva_meta["idade_arquivo_min"] = idade_min
        chuva_meta["mtime_arquivo"] = mtime.isoformat()
        from datetime import timedelta as _td
        _ref_slot = ts_origem.to_pydatetime() - _td(minutes=10)
        _slots_cand = [
            (_ref_slot - _td(days=d)).replace(hour=h, minute=5, second=0, microsecond=0)
            for d in (0, 1) for h in (0, 6, 12, 18)
        ]
        _slot_esperado = max(c for c in _slots_cand if c <= _ref_slot)
        chuva_meta["slot_esperado"] = _slot_esperado.isoformat()
        chuva_meta["stale_chuva"] = bool(mtime < _slot_esperado)

        df_r = pd.read_csv(RAIN_CSV, index_col=0, parse_dates=True)
        df_r.index = pd.to_datetime(df_r.index, errors="coerce")
        df_r = df_r.loc[~df_r.index.isna()].sort_index()

        # Passado observado (strictly <= ts_origem)
        df_past = df_r[df_r.index <= ts_origem]
        if not df_past.empty:
            s_o = df_past[[c for c in COLS_OESTE if c in df_past.columns]].mean(axis=1)
            s_n = df_past[[c for c in COLS_NORTE if c in df_past.columns]].mean(axis=1)
            s_l = df_past[[c for c in COLS_LESTE if c in df_past.columns]].mean(axis=1)

            chuva_meta["obs_oeste_lag_8_12h_mm"] = round(float(s_o.iloc[-13:-8].sum()) if len(s_o) >= 13 else float(s_o.sum()), 3)
            chuva_meta["obs_norte_lag_5_8h_mm"] = round(float(s_n.iloc[-9:-5].sum()) if len(s_n) >= 9 else float(s_n.sum()), 3)
            chuva_meta["obs_leste_lag_4_6h_mm"] = round(float(s_l.iloc[-7:-4].sum()) if len(s_l) >= 7 else float(s_l.sum()), 3)
            chuva_meta["obs_bacia_6h_mm"] = round(float(df_past.mean(axis=1).iloc[-6:].sum()), 3)

        # Previsao horaria disponivel na origem (ts_origem < t <= ts_origem + h)
        for h_str, h_num in HORIZONTES.items():
            ts_lim = ts_origem + pd.Timedelta(hours=h_num)
            df_fut = df_r[(df_r.index > ts_origem) & (df_r.index <= ts_lim)]
            if not df_fut.empty:
                chuva_meta["prev_oeste_mm"][h_str] = round(float(df_fut[[c for c in COLS_OESTE if c in df_fut.columns]].mean(axis=1).sum()), 3)
                chuva_meta["prev_norte_mm"][h_str] = round(float(df_fut[[c for c in COLS_NORTE if c in df_fut.columns]].mean(axis=1).sum()), 3)
                chuva_meta["prev_leste_mm"][h_str] = round(float(df_fut[[c for c in COLS_LESTE if c in df_fut.columns]].mean(axis=1).sum()), 3)

    # 5. Telemetria observada Defesa Civil SC (ultimo snapshot <= ts_origem com idade <= 120 min)
    dcsc_meta = {"disponivel": False, "max_6h_mm": 0.0, "max_24h_mm": 0.0, "atraso_min": None}
    if DCSC_HIST.exists():
        melhor_ts, melhor_reg = None, None
        for linha in DCSC_HIST.read_text(encoding="utf-8", errors="ignore").splitlines()[-30:]:
            if not linha.strip():
                continue
            try:
                reg = json.loads(linha)
                ts_r = pd.Timestamp(reg.get("timestamp_coleta") or reg.get("timestamp"))
                if ts_r.tzinfo is not None:
                    ts_r = ts_r.tz_convert("America/Sao_Paulo").tz_localize(None)
                if ts_r <= ts_origem and (ts_origem - ts_r) <= pd.Timedelta(minutes=120):
                    if melhor_ts is None or ts_r > melhor_ts:
                        melhor_ts, melhor_reg = ts_r, reg
            except Exception:
                continue
        if melhor_reg:
            c6s = [float(e["chuva_6h_mm"]) for e in melhor_reg.get("estacoes", []) if e.get("chuva_6h_mm") is not None]
            c24s = [float(e["chuva_24h_mm"]) for e in melhor_reg.get("estacoes", []) if e.get("chuva_24h_mm") is not None]
            dcsc_meta = {
                "disponivel": True,
                "max_6h_mm": round(max(c6s), 2) if c6s else 0.0,
                "max_24h_mm": round(max(c24s), 2) if c24s else 0.0,
                "atraso_min": round((ts_origem - melhor_ts).total_seconds() / 60.0, 2),
            }

    snapshot = _limpar_nan({
        "ts_origem": ts_origem.isoformat(),
        "erab": {
            "ts_leitura": ts_erab.isoformat(),
            "cota_cm": cota_origem,
            "vz_cm_h": vz_atual,
            "az_cm_h2": az_atual,
            "regime": regime_obs,
            "idade_min": idade_erab_min,
            "stale": bool(idade_erab_min > 45.0),
        },
        "chuva_bacia": chuva_meta,
        "defesa_civil_sc": dcsc_meta,
        "contorno_jusante": jusante,
        "v8_ciclo": v8_rows,
    })

    run_id = f"run_{ts_origem.strftime('%Y%m%d_%H%M%S')}"
    snapshot_hash = _sha256_obj(snapshot)
    return {
        "run_id": run_id,
        "ts_origem": ts_origem,
        "ts_leitura_erab": ts_erab,
        "cota_origem_cm": cota_origem,
        "regime_observado": regime_obs,
        "snapshot_hash": snapshot_hash,
        "snapshot_dados": snapshot,
    }


def _calcular_fisica_v1(snapshot: dict, h_str: str) -> tuple[float, dict, str]:
    """
    Avalia o modelo fisico enxuto de 5 termos congelados (feature_schema_version='fisica_v1.0').
    Retorna (y_pred_delta_cm, componentes_json, features_hash).
    """
    p = PARAMS_FISICA_V1[h_str]
    erab = snapshot["erab"]
    ch = snapshot["chuva_bacia"]
    dc = snapshot["defesa_civil_sc"]
    jus = snapshot["contorno_jusante"]

    # Termos 1, 2 e 3: Chuva efetiva prevista por braco (exclusivamente da previsao disponivel na origem)
    chuva_efetiva_oeste = float(ch["prev_oeste_mm"][h_str])
    chuva_efetiva_norte = float(ch["prev_norte_mm"][h_str])
    chuva_efetiva_leste = float(ch["prev_leste_mm"][h_str])

    # Termo 4: Estado hidrologico dos afluentes (pulso observado alinhado pelos lags fisicos + inercia local)
    pulso_oeste = float(ch["obs_oeste_lag_8_12h_mm"])
    pulso_norte = float(ch["obs_norte_lag_5_8h_mm"])
    pulso_leste = float(ch["obs_leste_lag_4_6h_mm"])
    pulso_dcsc = float(dc["max_6h_mm"]) if dc.get("disponivel") else 0.0

    # Combinacao fixa e documentada (pesos hidrologicos de area/resposta definidos a priori)
    estado_hidrologico_afluentes = round(
        0.35 * pulso_oeste + 0.45 * pulso_norte + 0.20 * max(pulso_leste, 0.25 * pulso_dcsc),
        4,
    )

    # Termo 5: Anomalia de contorno de jusante (componentes separados para rastreabilidade; peso 0.0 a priori)
    anomalia_contorno_jusante = float(jus["mare_anomalia_m"]) if jus.get("mare_anomalia_m") is not None else 0.0

    # Contribuicao da tendencia local amortecida
    vz = float(erab["vz_cm_h"])
    contrib_inercia_vz = p["k_vz"] * vz * (1.0 - math.exp(-HORIZONTES[h_str] / p["tau_vz"]))
    contrib_estado_afluentes = p["c_estado"] * estado_hidrologico_afluentes
    contrib_chuva_prevista = (
        p["c_oeste"] * chuva_efetiva_oeste
        + p["c_norte"] * chuva_efetiva_norte
        + p["c_leste"] * chuva_efetiva_leste
    )
    contrib_jusante = p["c_jusante"] * anomalia_contorno_jusante

    y_pred = round(contrib_inercia_vz + contrib_estado_afluentes + contrib_chuva_prevista + contrib_jusante, 4)

    componentes = _limpar_nan({
        "termos_fisica_v1_0": {
            f"chuva_efetiva_oeste_{h_str}": chuva_efetiva_oeste,
            f"chuva_efetiva_norte_{h_str}": chuva_efetiva_norte,
            f"chuva_efetiva_leste_{h_str}": chuva_efetiva_leste,
            "estado_hidrologico_afluentes": estado_hidrologico_afluentes,
            "anomalia_contorno_jusante": anomalia_contorno_jusante,
        },
        "subcomponentes_observados": {
            "vz_cm_h": vz,
            "obs_oeste_lag_8_12h_mm": pulso_oeste,
            "obs_norte_lag_5_8h_mm": pulso_norte,
            "obs_leste_lag_4_6h_mm": pulso_leste,
            "dcsc_max_6h_mm": pulso_dcsc,
            "jusante_mare_msl_m": jus.get("mare_msl_m"),
            "jusante_mare_delta_3h_m": jus.get("mare_delta_3h_m"),
            "jusante_componente_sul_kmh": jus.get("componente_sul_kmh"),
        },
        "contribuicoes_cm": {
            "inercia_vz_cm": round(contrib_inercia_vz, 4),
            "estado_afluentes_cm": round(contrib_estado_afluentes, 4),
            "chuva_prevista_cm": round(contrib_chuva_prevista, 4),
            "contorno_jusante_cm": round(contrib_jusante, 4),
        },
        "metadados_previsao_chuva": {
            "fonte": ch["fonte"],
            "janela_h": HORIZONTES[h_str],
            "unidades": ch["unidades"],
            "ponderacao": ch["ponderacao_espacial"],
            "idade_arquivo_min": ch["idade_arquivo_min"],
            "stale_chuva": ch["stale_chuva"],
            "slot_esperado": ch.get("slot_esperado"),
        },
        "parametros_congelados": p,
    })
    return y_pred, componentes, _sha256_obj(componentes)


def executar_backfill_prospectivo(conn) -> int:
    """Preenche y_true_delta_cm para previsoes prospectivas cujo ts_alvo ja venceu."""
    cur = conn.cursor()
    cur.execute(
        """
        SELECT forecast_id, ts_alvo, cota_origem_cm
        FROM forecast_predictions
        WHERE y_true_delta_cm IS NULL
          AND ts_alvo <= NOW() - INTERVAL '15 minutes'
        ORDER BY ts_alvo ASC;
        """
    )
    pendentes = cur.fetchall()
    atualizados = 0

    for fid, ts_alvo, cota_orig in pendentes:
        cur.execute(
            """
            SELECT timestamp, cota_cm,
                   ABS(EXTRACT(EPOCH FROM (timestamp - %s::timestamp)) / 60.0) AS desvio_min
            FROM leituras
            WHERE qc = 'VALIDO'
              AND cota_cm IS NOT NULL
              AND timestamp BETWEEN %s::timestamp - INTERVAL '25 minutes'
                                AND %s::timestamp + INTERVAL '25 minutes'
            ORDER BY desvio_min ASC
            LIMIT 1;
            """,
            (ts_alvo, ts_alvo, ts_alvo),
        )
        match = cur.fetchone()
        if match:
            ts_real, cota_real, desvio_min = match
            y_true = round(float(cota_real) - float(cota_orig), 4)
            cur.execute(
                """
                UPDATE forecast_predictions
                SET y_true_delta_cm = %s,
                    cota_alvo_real_cm = %s,
                    ts_leitura_alvo = %s,
                    desvio_alvo_min = %s
                WHERE forecast_id = %s;
                """,
                (y_true, float(cota_real), ts_real, round(float(desvio_min), 2), fid),
            )
            atualizados += 1

    conn.commit()
    cur.close()
    return atualizados


def rodar_ciclo_prospectivo() -> None:
    conn = get_postgres_connection()
    try:
        run = _coletar_snapshot_unificado(conn)
        snap = run["snapshot_dados"]
        ts_orig = run["ts_origem"]
        cota_orig = run["cota_origem_cm"]
        erab_stale = bool(snap["erab"]["stale"])

        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO forecast_runs (
                run_id, ts_origem, ts_leitura_erab, cota_origem_cm,
                regime_observado, snapshot_hash, snapshot_dados
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
            ON CONFLICT (run_id) DO NOTHING;
            """,
            (
                run["run_id"],
                ts_orig.to_pydatetime(),
                run["ts_leitura_erab"].to_pydatetime(),
                cota_orig,
                run["regime_observado"],
                run["snapshot_hash"],
                json.dumps(snap, ensure_ascii=False),
            ),
        )

        inseridos = 0
        for h_str, h_num in HORIZONTES.items():
            ts_alvo = (ts_orig + pd.Timedelta(hours=h_num)).to_pydatetime()

            # 1. Baseline: Persistencia (delta = 0)
            comp_pers = {"regra": "delta_z_zero", "cota_origem_cm": cota_orig}
            cur.execute(
                """
                INSERT INTO forecast_predictions (
                    run_id, model_name, model_version, feature_schema_version,
                    ts_origem, ts_predicao, horizonte, ts_alvo, cota_origem_cm,
                    y_pred_delta_cm, stale, valido, status_execucao, features_hash, componentes_json
                )
                VALUES (%s, 'persistencia', 'v1.0', 'persistencia_v1.0', %s, %s, %s, %s, %s, 0.0, %s, %s, 'OK', %s, %s::jsonb)
                ON CONFLICT (run_id, model_name, model_version, horizonte) DO NOTHING;
                """,
                (
                    run["run_id"], ts_orig.to_pydatetime(), ts_orig.to_pydatetime(),
                    h_str, ts_alvo, cota_orig, erab_stale, not erab_stale,
                    _sha256_obj(comp_pers), json.dumps(comp_pers),
                ),
            )
            inseridos += cur.rowcount

            # 2. Producao atual: v8_final_bacia (pareado sobre a mesma origem)
            v8_info = snap["v8_ciclo"].get(h_str)
            if v8_info and v8_info.get("y_pred_delta_cm") is not None:
                v8_stale = bool(erab_stale or v8_info.get("stale", False))
                v8_valido = bool(not erab_stale and v8_info.get("valido", True))
                cur.execute(
                    """
                    INSERT INTO forecast_predictions (
                        run_id, model_name, model_version, feature_schema_version,
                        ts_origem, ts_predicao, horizonte, ts_alvo, cota_origem_cm,
                        y_pred_delta_cm, stale, valido, status_execucao, features_hash, componentes_json
                    )
                    VALUES (%s, 'v8_final_bacia', 'v8_final_bacia', 'v8_bacia_8f', %s, %s, %s, %s, %s, %s, %s, %s, 'OK', %s, %s::jsonb)
                    ON CONFLICT (run_id, model_name, model_version, horizonte) DO NOTHING;
                    """,
                    (
                        run["run_id"], ts_orig.to_pydatetime(),
                        datetime.fromisoformat(v8_info["ts_predicao"]),
                        h_str, ts_alvo, cota_orig,
                        float(v8_info["y_pred_delta_cm"]), v8_stale, v8_valido,
                        v8_info.get("features_hash"),
                        json.dumps({"origem": "predicoes_shadow_pareado", "v8_info": v8_info}),
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO forecast_predictions (
                        run_id, model_name, model_version, feature_schema_version,
                        ts_origem, ts_predicao, horizonte, ts_alvo, cota_origem_cm,
                        y_pred_delta_cm, stale, valido, status_execucao, motivo_falha
                    )
                    VALUES (%s, 'v8_final_bacia', 'v8_final_bacia', 'v8_bacia_8f', %s, %s, %s, %s, %s, NULL, TRUE, FALSE, 'FALHA_COLETA', 'v8_ausente_na_janela_20min')
                    ON CONFLICT (run_id, model_name, model_version, horizonte) DO NOTHING;
                    """,
                    (run["run_id"], ts_orig.to_pydatetime(), ts_orig.to_pydatetime(), h_str, ts_alvo, cota_orig),
                )
            inseridos += cur.rowcount

            # 3. Candidato fisico enxuto: fisica_3bracos v1.0 (feature_schema_version='fisica_v1.0')
            y_fis, comp_fis, hash_fis = _calcular_fisica_v1(snap, h_str)
            fis_stale = bool(erab_stale or snap["chuva_bacia"]["stale_chuva"])
            cur.execute(
                """
                INSERT INTO forecast_predictions (
                    run_id, model_name, model_version, feature_schema_version,
                    ts_origem, ts_predicao, horizonte, ts_alvo, cota_origem_cm,
                    y_pred_delta_cm, stale, valido, status_execucao, features_hash, componentes_json
                )
                VALUES (%s, 'fisica_3bracos', 'v1.0', 'fisica_v1.0', %s, %s, %s, %s, %s, %s, %s, %s, 'OK', %s, %s::jsonb)
                ON CONFLICT (run_id, model_name, model_version, horizonte) DO NOTHING;
                """,
                (
                    run["run_id"], ts_orig.to_pydatetime(), ts_orig.to_pydatetime(),
                    h_str, ts_alvo, cota_orig, y_fis, fis_stale, not erab_stale,
                    hash_fis, json.dumps(comp_fis, ensure_ascii=False),
                ),
            )
            inseridos += cur.rowcount

        conn.commit()
        cur.close()

        n_bf = executar_backfill_prospectivo(conn)
        LOGGER.info(
            "[OK] Rodada prospectiva %s | cota=%.1f cm | predictions_inseridas=%d | backfill_y_true=%d",
            run["run_id"], cota_orig, inseridos, n_bf,
        )
    finally:
        conn.close()


if __name__ == "__main__":
    rodar_ciclo_prospectivo()
