import json
import math
import sys
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[2]
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.relatorios.monitor_continuo import determinar_qc
from src.relatorios.postgres_db import get_postgres_connection

import pandas as pd

import json
CHUVA_CSV = BASE / "data" / "chuva_bacia_openmeteo.csv"
CHUVA_DCSC_JSON = BASE / "data" / "chuva_defesacivil_realtime.json"
PROVENIENCIA_JSONL = BASE / "data" / "proveniencia_observacoes.jsonl"


def _avaliar_fontes_chuva(max_idade_horas: float = 2.0) -> dict:
    """Preserva valores originais por fonte/estacao com timestamps e calcula estimativa conservadora."""
    agora = datetime.now()
    chuva_om = None
    try:
        df = pd.read_csv(CHUVA_CSV, index_col=0, parse_dates=True)
        if not df.empty:
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df.loc[~df.index.isna()].sort_index()
            corte = pd.Timestamp.now() - pd.Timedelta(hours=24)
            janela = df[df.index >= corte]
            if not janela.empty:
                chuva_om = round(float(janela.mean(axis=1).sum()), 3)
    except Exception as e:
        print(f"[AVISO] Falha ao ler Open-Meteo: {e}")

    chuva_dc_max = None
    dc_fresco = False
    dc_atraso_min = None
    dc_ts_coleta = None
    estacoes_detalhe = []

    try:
        if CHUVA_DCSC_JSON.exists():
            dados = json.loads(CHUVA_DCSC_JSON.read_text(encoding="utf-8"))
            dc_ts_coleta = dados.get("timestamp_coleta")
            if dc_ts_coleta:
                dt_col = datetime.fromisoformat(dc_ts_coleta)
                dc_atraso_min = round((agora - dt_col).total_seconds() / 60.0, 1)
                dc_fresco = (dc_atraso_min / 60.0) <= max_idade_horas
            for est in dados.get("estacoes", []):
                atraso_est_min = None
                ts_est_str = est.get("atualizacao_estacao")
                if ts_est_str:
                    try:
                        dt_est = datetime.strptime(ts_est_str, "%d/%m/%Y %H:%M:%S")
                        atraso_est_min = round((agora - dt_est).total_seconds() / 60.0, 1)
                    except ValueError:
                        pass
                estacoes_detalhe.append({
                    "codigo": est.get("codigo"),
                    "trecho_bacia": est.get("trecho_bacia"),
                    "ts_medido": ts_est_str,
                    "atraso_min": atraso_est_min,
                    "chuva_1h_mm": est.get("chuva_1h_mm"),
                    "chuva_6h_mm": est.get("chuva_6h_mm"),
                    "chuva_24h_mm": est.get("chuva_24h_mm"),
                    "rio_m": est.get("rio_m"),
                })
            if dc_fresco:
                val = dados.get("pior_caso_bacia", {}).get("max_chuva_24h_mm")
                if val is not None:
                    chuva_dc_max = round(float(val), 3)
    except Exception as e:
        print(f"[AVISO] Falha ao ler Defesa Civil SC: {e}")

    candidatos = {}
    if chuva_om is not None:
        candidatos["OPEN_METEO_GRADE_8PTS"] = chuva_om
    if chuva_dc_max is not None:
        candidatos["DEFESA_CIVIL_SC_TELEMETRIA"] = chuva_dc_max

    if candidatos:
        fonte_dominante = max(candidatos, key=candidatos.get)
        estimativa_conservadora = candidatos[fonte_dominante]
    else:
        fonte_dominante = "NENHUMA_DISPONIVEL"
        estimativa_conservadora = None

    registro = {
        "ts_ciclo_gravacao": agora.isoformat(timespec="seconds"),
        "criterio_fusao": "ESTIMATIVA_CONSERVADORA_MAX",
        "fonte_dominante": fonte_dominante,
        "estimativa_conservadora_24h_mm": estimativa_conservadora,
        "fontes_originais": {
            "open_meteo_media_bacia_24h_mm": chuva_om,
            "defesa_civil_sc": {
                "ts_coleta": dc_ts_coleta,
                "atraso_coleta_min": dc_atraso_min,
                "fresco": dc_fresco,
                "max_24h_mm": chuva_dc_max,
                "estacoes": estacoes_detalhe,
            },
        },
    }

    try:
        with open(PROVENIENCIA_JSONL, "a", encoding="utf-8") as f:
            f.write(json.dumps(registro, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[AVISO] Falha ao gravar proveniencia_observacoes.jsonl: {e}")

    return registro


def calcular_chuva_24h():
    """Retorna a estimativa conservadora 24h e registra a proveniencia completa das fontes."""
    reg = _avaliar_fontes_chuva()
    return reg.get("estimativa_conservadora_24h_mm")


REGIME_FILE = BASE / "data" / "regime_atual.json"
COTA_FILE = BASE / "tubarao_saneamento_dados.json"


def gravar_leitura(regime, dados_cota, connection_factory=get_postgres_connection):
    cota_cm = dados_cota.get("cota_cm")
    qc_fonte = dados_cota.get("qc")
    ts_coleta = dados_cota.get("data_extracao")
    connection = connection_factory()
    try:
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT cota_cm
                FROM leituras
                WHERE cota_cm IS NOT NULL
                ORDER BY timestamp DESC, id DESC
                LIMIT 1
            """)
            anterior = cursor.fetchone()
            cota_anterior = anterior[0] if anterior else None
            qc = determinar_qc(cota_cm, cota_anterior, qc_fonte)

            if cota_cm is not None:
                try:
                    cota_cm = float(cota_cm)
                except (TypeError, ValueError):
                    cota_cm = None
                    qc = "CORROMPIDO"
                else:
                    if not math.isfinite(cota_cm) or cota_cm <= 0:
                        cota_cm = None
                        qc = "CORROMPIDO"

            cursor.execute("""
                INSERT INTO leituras (
                    timestamp, ts_coleta, cota_cm, vz_cm_h, az_cm_h2, regime,
                    chuva_pior_caso_mm, qc
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                datetime.now(),
                ts_coleta,
                cota_cm,
                regime.get("delta_60m"),
                regime.get("aceleracao_az"),
                regime.get("regime") or "DESCONHECIDO",
                calcular_chuva_24h(),
                qc,
            ))
        connection.commit()
        return qc
    finally:
        connection.close()


def main():
    if not REGIME_FILE.exists():
        print("regime_atual.json não encontrado; nenhuma leitura foi gravada.")
        return

    with REGIME_FILE.open("r", encoding="utf-8") as file:
        regime = json.load(file)
    if COTA_FILE.exists():
        with COTA_FILE.open("r", encoding="utf-8") as file:
            dados_cota = json.load(file)
    else:
        dados_cota = {}

    qc = gravar_leitura(regime, dados_cota)
    print(
        "Leitura gravada no PostgreSQL: "
        f"QC={qc}, vz={regime.get('delta_60m')}, "
        f"az={regime.get('aceleracao_az')}, "
        f"regime={regime.get('regime', 'NORMAL')}"
    )


if __name__ == "__main__":
    main()
