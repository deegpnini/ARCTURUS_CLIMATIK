#!/usr/bin/env python3
"""
dashboard_kpis.py — Provedor unificado de KPIs operacionais do Dashboard ARCTURUS.
Usa exatamente a mesma régua, fontes e projeções em modo sombra do boletim_telegram.py.
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


def _classificar_chuva_unificada(chuva_mm: float):
    if chuva_mm >= 60.0:
        return "EXTREMO", "#dc2626"
    if chuva_mm >= 30.0:
        return "ALERTA", "#f97316"
    if chuva_mm >= 15.0:
        return "ATENÇÃO", "#eab308"
    if chuva_mm >= 5.0:
        return "NORMAL", "#22c55e"
    return "BAIXO", "#38bdf8"


def _classificar_rio_unificado(cota_cm: float, vz_cm_h: float):
    if cota_cm >= 600.0:
        return "EXTREMO", "#dc2626"
    if cota_cm >= 350.0:
        return "ALERTA", "#f97316"
    if cota_cm >= 250.0 or vz_cm_h >= 5.0:
        return "ATENÇÃO", "#eab308"
    if cota_cm >= 50.0:
        return "NORMAL", "#22c55e"
    return "BAIXO", "#38bdf8"


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
        "estado_chuva": "NORMAL",
        "estado_chuva_cor": "#22c55e",
        "estado_rio": "NORMAL",
        "estado_rio_cor": "#22c55e",
        "estado_operacional": "NORMAL",
        "estado_cor": "#22c55e",
        "dcsc_validas": "0/6",
        "dcsc_idade_min": None,
        "evento_id": None,
        "sombra_resumo": "Indisponível",
        "sombra_detalhe": "Modo sombra • Aguardando ciclo",
        "sombra_stale": True,
    }

    # 1. PostgreSQL: cota atual, velocidade, aceleração, mínimo 24h e projeção sombra
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

            # Mesma regra semântica de tendência do Telegram
            if vz >= 2.0:
                dados["tendencia_label"] = f"SUBINDO (+{vz:.1f} cm/h)"
                dados["tendencia_cor"] = "#ef4444"
            elif vz > 0.5:
                dados["tendencia_label"] = f"ELEVAÇÃO (+{vz:.1f} cm/h)"
                dados["tendencia_cor"] = "#f59e0b"
            elif vz <= -2.0:
                dados["tendencia_label"] = f"ESTÁVEL / RECESSÃO ({vz:.1f} cm/h)"
                dados["tendencia_cor"] = "#38bdf8"
            else:
                dados["tendencia_label"] = f"ESTÁVEL ({vz:+.1f} cm/h)"
                dados["tendencia_cor"] = "#22c55e"

        cur.execute("""
            SELECT MIN(cota_cm)
            FROM leituras
            WHERE cota_cm IS NOT NULL
              AND timestamp >= NOW() - INTERVAL '24 hours'
        """)
        min_row = cur.fetchone()
        if min_row and min_row[0] is not None and dados["cota_cm"] is not None:
            dados["delta_24h_cm"] = round(dados["cota_cm"] - float(min_row[0]), 1)

        # Projeções experimentais (predicoes_shadow) idênticas ao boletim Telegram
        cur.execute("""
            SELECT timestamp, horizonte, y_score, stale
            FROM predicoes_shadow
            WHERE timestamp = (SELECT MAX(timestamp) FROM predicoes_shadow)
            ORDER BY CASE horizonte WHEN '1h' THEN 1 WHEN '3h' THEN 2 WHEN '6h' THEN 3 ELSE 4 END
        """)
        sombra_rows = cur.fetchall()
        if sombra_rows:
            partes = []
            algum_stale = False
            ts_sombra = sombra_rows[0][0]
            for _, hor, y_sc, st in sombra_rows:
                val_cm = int(round(float(y_sc)))
                sinal = "−" if val_cm < 0 else ("+" if val_cm > 0 else "")
                partes.append(f"{hor} {sinal}{abs(val_cm)} cm")
                if st:
                    algum_stale = True
            dados["sombra_resumo"] = " · ".join(partes)
            dados["sombra_stale"] = algum_stale
            ts_s_str = ts_sombra.strftime("%H:%M") if hasattr(ts_sombra, "strftime") else str(ts_sombra)[11:16]
            tag_stale = " (defasado)" if algum_stale else ""
            dados["sombra_detalhe"] = f"Modo sombra ({ts_s_str}){tag_stale} • Não é alerta oficial"

        cur.close()
        conn.close()
    except Exception:
        pass

    # 2. Telemetria real da Defesa Civil SC (fonte primária de chuva observada 24h)
    dcsc_ok = False
    if DCSC_FILE.exists():
        try:
            dc = json.loads(DCSC_FILE.read_text(encoding="utf-8"))
            ests = dc.get("estacoes", [])
            validas = [e for e in ests if e.get("chuva_24h_mm") is not None]
            dados["dcsc_validas"] = f"{len(validas)}/{len(ests) or 6}"
            if validas:
                top = max(validas, key=lambda x: float(x.get("chuva_24h_mm") or 0))
                dados["chuva_max_24h_mm"] = float(top["chuva_24h_mm"])
                dados["estacao_dominante"] = top.get("trecho_bacia") or top.get("nome_oficial", "DCSC")
                dados["chuva_6h_mm"] = max(float(e.get("chuva_6h_mm") or 0) for e in validas)
                dcsc_ok = True
            ts_col = dc.get("timestamp_coleta")
            if ts_col:
                dt_col = datetime.fromisoformat(str(ts_col).replace("Z", "+00:00")).replace(tzinfo=None)
                dados["dcsc_idade_min"] = max(0, int((datetime.now() - dt_col).total_seconds() // 60))
        except Exception:
            pass

    # Fallback para proveniencia_observacoes.jsonl apenas se DCSC não tiver estação válida
    if not dcsc_ok and PROV_FILE.exists():
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

    # 3. Classificação Unificada (Chuva vs Rio — mesma régua do Telegram)
    cota = dados["cota_cm"] or 0.0
    chuva = dados["chuva_max_24h_mm"] or 0.0
    vz = dados["vz_cm_h"] or 0.0

    est_chuva, cor_chuva = _classificar_chuva_unificada(chuva)
    est_rio, cor_rio = _classificar_rio_unificado(cota, vz)
    dados["estado_chuva"] = est_chuva
    dados["estado_chuva_cor"] = cor_chuva
    dados["estado_rio"] = est_rio
    dados["estado_rio_cor"] = cor_rio

    ordem = {"BAIXO": 0, "NORMAL": 1, "ATENÇÃO": 2, "ALERTA": 3, "EXTREMO": 4}
    if ordem[est_rio] >= ordem[est_chuva]:
        dados["estado_operacional"] = f"RIO: {est_rio}"
        dados["estado_cor"] = cor_rio
    else:
        dados["estado_operacional"] = f"CHUVA: {est_chuva}"
        dados["estado_cor"] = cor_chuva

    # 4. Evento ativo em lag_eventos.jsonl
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
