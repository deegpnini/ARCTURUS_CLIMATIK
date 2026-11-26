#!/usr/bin/env python3
"""
verificador_previsoes.py — Compara previsões vencidas (ts_alvo <= agora)
com a cota real (y_true) e classifica o acerto.
Grava em data/verificacao_previsoes.json e loga em logs/verificador.log.
"""
import json
import logging
from datetime import datetime
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE))

from src.relatorios.postgres_db import get_postgres_connection

LOG = logging.getLogger("verificador")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.FileHandler(BASE / "logs" / "verificador.log"),
        logging.StreamHandler(),
    ],
)

# Limiares de classificação (em cm)
LIMIAR_EXATO = 2.0
LIMIAR_APROXIMADO = 5.0
LIMIAR_MODERADO = 10.0

def classificar(diff_abs):
    if diff_abs <= LIMIAR_EXATO:
        return "EXATO"
    elif diff_abs <= LIMIAR_APROXIMADO:
        return "APROXIMADO"
    elif diff_abs <= LIMIAR_MODERADO:
        return "MODERADO"
    else:
        return "GRAVE"

def verificar():
    conn = get_postgres_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, modelo, horizonte, timestamp, y_score, y_true
        FROM predicoes_shadow
        WHERE y_true IS NOT NULL
          AND valido = true
          AND ts_observacao <= NOW()
        ORDER BY timestamp DESC
        LIMIT 200
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        LOG.info("Nenhuma previsão vencida para verificar")
        return

    verificacoes = []
    for row in rows:
        pid, modelo, horizonte, timestamp, y_pred, y_true = row
        diff = y_pred - y_true
        diff_abs = abs(diff)
        classificacao = classificar(diff_abs)
        verificacoes.append({
            "id": pid,
            "modelo": modelo,
            "horizonte": horizonte,
            "timestamp": timestamp.isoformat() if timestamp else None,
            "y_pred_cm": round(float(y_pred), 2),
            "y_true_cm": round(float(y_true), 2),
            "diff_cm": round(float(diff), 2),
            "diff_abs_cm": round(float(diff_abs), 2),
            "classificacao": classificacao,
        })

    # Resumo por horizonte
    resumo = {}
    for h in ["1h", "3h", "6h"]:
        sub = [v for v in verificacoes if v["horizonte"] == h]
        if not sub:
            continue
        total = len(sub)
        exatos = sum(1 for v in sub if v["classificacao"] == "EXATO")
        aproximados = sum(1 for v in sub if v["classificacao"] == "APROXIMADO")
        moderados = sum(1 for v in sub if v["classificacao"] == "MODERADO")
        graves = sum(1 for v in sub if v["classificacao"] == "GRAVE")
        mae = sum(v["diff_abs_cm"] for v in sub) / total
        resumo[h] = {
            "total": total,
            "exatos": exatos,
            "aproximados": aproximados,
            "moderados": moderados,
            "graves": graves,
            "mae_cm": round(mae, 2),
            "taxa_acerto_exato": round(100 * exatos / total, 1),
            "taxa_acerto_aproximado": round(100 * (exatos + aproximados) / total, 1),
        }

    resultado = {
        "timestamp": datetime.now().isoformat(),
        "total_verificacoes": len(verificacoes),
        "resumo": resumo,
        "verificacoes": verificacoes,
    }

    saida = BASE / "data" / "verificacao_previsoes.json"
    saida.write_text(json.dumps(resultado, indent=2, ensure_ascii=False), encoding="utf-8")
    LOG.info(f"Verificação concluída: {len(verificacoes)} previsões")
    for h, r in resumo.items():
        LOG.info(
            f"  {h}: n={r['total']} | MAE={r['mae_cm']} cm | "
            f"exato={r['taxa_acerto_exato']}% | aproximado={r['taxa_acerto_aproximado']}% | "
            f"graves={r['graves']}"
        )

if __name__ == "__main__":
    verificar()
