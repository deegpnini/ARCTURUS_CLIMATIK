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


def _ler_chuva_defesacivil_24h(max_idade_horas: float = 2.0):
    """Retorna o maior acumulado 24h da Defesa Civil SC se o snapshot estiver fresco."""
    try:
        if not CHUVA_DCSC_JSON.exists():
            return None
        dados = json.loads(CHUVA_DCSC_JSON.read_text(encoding="utf-8"))
        ts_str = dados.get("timestamp_coleta")
        if ts_str:
            ts_coleta = datetime.fromisoformat(ts_str)
            idade_h = (datetime.now() - ts_coleta).total_seconds() / 3600.0
            if idade_h > max_idade_horas:
                return None
        val = dados.get("pior_caso_bacia", {}).get("max_chuva_24h_mm")
        return float(val) if val is not None else None
    except Exception as e:
        print(f"[AVISO] Falha ao ler chuva Defesa Civil SC: {e}")
        return None


def calcular_chuva_24h():
    """Funde a chuva 24h da Open-Meteo (grade) com a Defesa Civil SC (telemetria fisica)."""
    chuva_om = None
    try:
        df = pd.read_csv(CHUVA_CSV, index_col=0, parse_dates=True)
        if not df.empty:
            df.index = pd.to_datetime(df.index, errors="coerce")
            df = df.loc[~df.index.isna()].sort_index()
            corte = pd.Timestamp.now() - pd.Timedelta(hours=24)
            janela = df[df.index >= corte]
            if not janela.empty:
                chuva_om = float(janela.mean(axis=1).sum())
    except Exception as e:
        print(f"[AVISO] Falha ao calcular chuva_24h Open-Meteo: {e}")

    chuva_dc = _ler_chuva_defesacivil_24h()
    valores = [v for v in (chuva_om, chuva_dc) if v is not None]
    if not valores:
        return None
    return max(valores)


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
