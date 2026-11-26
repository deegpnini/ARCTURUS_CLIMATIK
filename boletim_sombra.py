#!/usr/bin/env python3
"""
boletim_sombra.py — Compara a combinação por horizonte (v8 em 1h/3h,
fisica_3bracos em 6h) com o boletim oficial (LightGBM_v2 em predicoes_shadow).
Não envia nada. Só loga a comparação.
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
import logging
import pandas as pd

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from src.relatorios.postgres_db import get_postgres_connection

LOG = logging.getLogger("boletim_sombra")
(BASE / "logs").mkdir(parents=True, exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(BASE / "logs" / "boletim_sombra.log"),
        logging.StreamHandler(),
    ],
)

def obter_previsao_oficial(conn):
    """Última predição do LightGBM_v2 em predicoes_shadow (boletim oficial)."""
    cur = conn.cursor()
    cur.execute("""
        SELECT horizonte, y_score
        FROM predicoes_shadow
        WHERE timestamp > NOW() - INTERVAL '20 minutes'
          AND stale = false
        ORDER BY timestamp DESC, horizonte
        LIMIT 3
    """)
    rows = cur.fetchall()
    cur.close()
    return {h: float(y) for h, y in rows if y is not None}

def obter_previsao_sombra(conn):
    """Combinação por horizonte: v8 em 1h/3h, fisica_3bracos em 6h."""
    cur = conn.cursor()
    cur.execute("""
        SELECT horizonte, model_name, y_pred_delta_cm
        FROM forecast_predictions
        WHERE ts_origem > NOW() - INTERVAL '20 minutes'
          AND y_pred_delta_cm IS NOT NULL
          AND valido = true
        ORDER BY ts_origem DESC, horizonte, model_name
    """)
    rows = cur.fetchall()
    cur.close()

    # Pega a última rodada de cada modelo/horizonte
    ultima = {}
    for h, model, y in rows:
        key = (h, model)
        if key not in ultima:
            ultima[key] = float(y)

    # Combinação por horizonte
    combinacao = {}
    for h in ["1h", "3h"]:
        if (h, "v8_final_bacia") in ultima:
            combinacao[h] = ultima[(h, "v8_final_bacia")]
        elif (h, "fisica_3bracos") in ultima:
            combinacao[h] = ultima[(h, "fisica_3bracos")]
    if ("6h", "fisica_3bracos") in ultima:
        combinacao["6h"] = ultima[("6h", "fisica_3bracos")]
    elif ("6h", "v8_final_bacia") in ultima:
        combinacao["6h"] = ultima[("6h", "v8_final_bacia")]

    return combinacao

def obter_chuva_prevista(horas=6):
    """Soma da chuva prevista nas próximas N horas (CSV)."""
    csv = BASE / "data" / "chuva_bacia_openmeteo.csv"
    if not csv.exists():
        return 0.0
    try:
        df = pd.read_csv(csv, index_col=0, parse_dates=True)
        df.index = pd.to_datetime(df.index, errors="coerce")
        df = df.loc[~df.index.isna()].sort_index()
        agora = datetime.now()
        futuro = agora + timedelta(hours=horas)
        df_fut = df[(df.index > agora) & (df.index <= futuro)]
        if df_fut.empty:
            return 0.0
        return float(df_fut.sum(axis=1).sum())
    except Exception:
        return 0.0


def escolher_combinacao(oficial, sombra, chuva_6h):
    """Retorna a escolha condicional sem alterar ou enviar o boletim oficial."""
    if chuva_6h < 5.0:
        return "SECO", oficial
    return "CHUVA", sombra


def main():
    try:
        conn = get_postgres_connection()
    except Exception as exc:
        LOG.warning("Boletim sombra indisponível: banco não pôde ser conectado: %s", exc)
        return

    try:
        oficial = obter_previsao_oficial(conn)
        sombra = obter_previsao_sombra(conn)
    except Exception as exc:
        LOG.warning("Boletim sombra indisponível: falha ao consultar previsões: %s", exc)
        return
    finally:
        conn.close()

    if not oficial and not sombra:
        LOG.warning("Nenhuma previsão disponível (oficial ou sombra)")
        return

    LOG.info("=" * 70)
    LOG.info("COMPARAÇÃO: BOLETIM OFICIAL vs COMBINAÇÃO SOMBRA")
    LOG.info("=" * 70)

    chuva_6h = obter_chuva_prevista(horas=6)
    cenário, combinacao = escolher_combinacao(oficial, sombra, chuva_6h)
    if cenário == "SECO":
        LOG.info(f"Cenário SECO (chuva prevista 6h: {chuva_6h:.2f} mm < 5 mm)")
        LOG.info("→ Usando OFICIAL (LightGBM_v2) em todos os horizontes")
    else:
        LOG.info(f"Cenário de CHUVA (chuva prevista 6h: {chuva_6h:.2f} mm >= 5 mm)")
        LOG.info("→ Usando COMBINAÇÃO (v8 em 1h/3h, fisica_3bracos em 6h)")

    # Comparação: oficial vs a escolha condicional (combinacao)
    for h in ["1h", "3h", "6h"]:
        y_of = oficial.get(h)
        y_cb = combinacao.get(h)
        if y_of is None and y_cb is None:
            LOG.info(f"{h}: sem previsão")
            continue
        if y_of is None:
            LOG.info(f"{h}: oficial=INDISPONÍVEL | escolha={y_cb:+.1f} cm")
        elif y_cb is None:
            LOG.info(f"{h}: oficial={y_of:+.1f} cm | escolha=INDISPONÍVEL")
        else:
            diff = y_cb - y_of
            LOG.info(
                f"{h}: oficial={y_of:+.1f} cm | escolha={y_cb:+.1f} cm | "
                f"diferença={diff:+.1f} cm"
            )

    # Alerta apenas se a escolha condicional for mais conservadora (prevê mais subida)
    for h in ["1h", "3h", "6h"]:
        y_of = oficial.get(h)
        y_cb = combinacao.get(h)
        if y_of is not None and y_cb is not None and y_cb > y_of + 5:
            LOG.warning(
                f"⚠️ {h}: escolha condicional prevê {y_cb - y_of:+.1f} cm MAIS subida que o oficial. "
                f"Pode ser cheia que o oficial está subestimando."
            )

    LOG.info("=" * 70)

if __name__ == "__main__":
    main()
