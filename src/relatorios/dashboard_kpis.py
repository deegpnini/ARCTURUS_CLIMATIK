#!/usr/bin/env python3
"""
dashboard_kpis.py — Provedor 100% leitura para os KPIs operacionais do Dashboard ARCTURUS.
Consulta PostgreSQL (leituras), data/proveniencia_observacoes.jsonl e data/chuva_defesacivil_realtime.json.
"""
import json
import os
from datetime import datetime
from pathlib import Path
import psycopg2

BASE = Path(__file__).resolve().parents[2]
DB_URL = os.environ.get("DATABASE_URL", "postgresql:///arcturus")
PROV_FILE = BASE / "data" / "proveniencia_observacoes.jsonl"
DCSC_FILE = BASE / "data" / "chuva_defesacivil_realtime.json"
LAG_FILE = BASE / "data" / "lag_eventos.jsonl"


def obter_kpis_operacionais() -> dict:
    dados = {
        "cota_cm": None,
        "delta_24h_cm": None,
        "vz_cm_h": 0.0,
        "az_cm_h2": 0.0,
        "tendencia_label": "SEM DADOS",
        "tendencia_cor": "#94a3b8",
        "ts_leitura": "N/D",
        "chuva_max_24h_mm": 0.0,
        "estacao_dominante": "N/D",
        "chuva_6h_mm": 0.0,
        "estado_operacional": "NORMAL",
        "estado_cor": "#22c55e",
        "dcsc_validas": "0/6",
        "dcsc_idade_min": None,
        "evento_id": None,
    }

    # 1. PostgreSQL: cota atual, velocidade, aceleração e mínimo nas últimas 24h
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            SELECT timestamp, cota_cm, COALESCE(vz_cm_h, 0), COALESCE(az_cm_h2, 0), COALESCE(chuva_pior_caso_mm, 0)
            FROM leituras
            WHERE cota_cm IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 1
        """)
        row = cur.fetchone()
        if row:
            ts, cota, vz, az, chuva_db = row
            dados["cota_cm"] = float(cota)
            dados["vz_cm_h"] = float(vz)
            dados["az_cm_h2"] = float(az)
            dados["chuva_max_24h_mm"] = float(chuva_db)
            dados["ts_leitura"] = ts.strftime("%d/%m %H:%M") if hasattr(ts, "strftime") else str(ts)[:16]

            if vz >= 2.0:
                dados["tendencia_label"] = f"SUBINDO (+{vz:.1f} cm/h)"
                dados["tendencia_cor"] = "#ef4444"
            elif vz > 0.3:
                dados["tendencia_label"] = f"ELEVAÇÃO (+{vz:.1f} cm/h)"
                dados["tendencia_cor"] = "#f59e0b"
            elif vz <= -1.0:
                dados["tendencia_label"] = f"RECESSÃO ({vz:.1f} cm/h)"
                dados["tendencia_cor"] = "#38bdf8"
            else:
                dados["tendencia_label"] = f"ESTÁVEL / PLATÔ ({vz:+.1f} cm/h)"
                dados["tendencia_cor"] = "#eab308"

        cur.execute("""
            SELECT MIN(cota_cm)
            FROM leituras
            WHERE cota_cm IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '24 hours'
        """)
        min_row = cur.fetchone()
        if min_row and min_row[0] is not None and dados["cota_cm"] is not None:
            dados["delta_24h_cm"] = round(dados["cota_cm"] - float(min_row[0]), 1)

        cur.close()
        conn.close()
    except Exception:
        pass

    # 2. Proveniência temporal (última linha do JSONL)
    if PROV_FILE.exists():
        try:
            linhas = PROV_FILE.read_text(encoding="utf-8").strip().splitlines()
            if linhas:
                ult = json.loads(linhas[-1])
                c_cons = ult.get("chuva_conservadora_24h_mm")
                if c_cons is not None:
                    dados["chuva_max_24h_mm"] = float(c_cons)
                est_dom = ult.get("estacao_dominante_24h") or ult.get("fonte_dominante")
                if est_dom:
                    dados["estacao_dominante"] = str(est_dom)
        except Exception:
            pass

    # 3. Qualidade/Frescor Defesa Civil SC
    if DCSC_FILE.exists():
        try:
            dc = json.loads(DCSC_FILE.read_text(encoding="utf-8"))
            ests = dc.get("estacoes", [])
            validas = [e for e in ests if e.get("chuva_24h_mm") is not None]
            dados["dcsc_validas"] = f"{len(validas)}/{len(ests) or 6}"
            if validas:
                top = max(validas, key=lambda x: float(x.get("chuva_24h_mm") or 0))
                if float(top.get("chuva_24h_mm") or 0) >= dados["chuva_max_24h_mm"]:
                    dados["chuva_max_24h_mm"] = float(top["chuva_24h_mm"])
                    dados["estacao_dominante"] = top.get("trecho_bacia") or top.get("nome_oficial", "DCSC")
                dados["chuva_6h_mm"] = max(float(e.get("chuva_6h_mm") or 0) for e in validas)
            ts_col = dc.get("timestamp_coleta")
            if ts_col:
                dt_col = datetime.fromisoformat(str(ts_col).replace("Z", "+00:00")).replace(tzinfo=None)
                dados["dcsc_idade_min"] = max(0, int((datetime.now() - dt_col).total_seconds() // 60))
        except Exception:
            pass

    # 4. Classificação de Estado Operacional
    cota = dados["cota_cm"] or 0.0
    chuva = dados["chuva_max_24h_mm"] or 0.0
    vz = dados["vz_cm_h"] or 0.0
    if cota >= 600 or chuva >= 80:
        dados["estado_operacional"] = "EMERGÊNCIA"
        dados["estado_cor"] = "#dc2626"
    elif cota >= 400 or chuva >= 50 or vz >= 5.0:
        dados["estado_operacional"] = "ALERTA"
        dados["estado_cor"] = "#f97316"
    elif cota >= 250 or chuva >= 15 or vz >= 1.5 or (dados["delta_24h_cm"] or 0) >= 30:
        dados["estado_operacional"] = "ATENÇÃO"
        dados["estado_cor"] = "#eab308"
    else:
        dados["estado_operacional"] = "NORMAL"
        dados["estado_cor"] = "#22c55e"

    # 5. Evento ativo em lag_eventos.jsonl
    if LAG_FILE.exists():
        try:
            linhas_lag = LAG_FILE.read_text(encoding="utf-8").strip().splitlines()
            if linhas_lag:
                ev = json.loads(linhas_lag[-1])
                dados["evento_id"] = ev.get("evento_id")
        except Exception:
            pass

    return dados


if __name__ == "__main__":
    print(json.dumps(obter_kpis_operacionais(), indent=2, ensure_ascii=False))
