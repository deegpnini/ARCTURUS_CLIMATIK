#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv
from datetime import datetime

DB_URL = os.environ.get("DATABASE_URL", "postgresql:///arcturus")
MODELO = "LightGBM_v2"
VERSAO = "2.0.0"

def persistir_postgres(
    timestamp,
    evento_id,
    y_pred,
    y_true,
    horizonte,
    cota_atual,
    ts_observacao=None,
    ts_predicao=None,
    model_version=None,
    features_hash=None,
):
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO predicoes_shadow
            (
                timestamp, modelo, versao, evento_id, y_true, y_score,
                horizonte, threshold, ts_observacao, ts_predicao,
                model_version, features_hash
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (
            timestamp, MODELO, VERSAO, evento_id, y_true, y_pred, horizonte,
            None, ts_observacao, ts_predicao, model_version, features_hash,
        ))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[AVISO] PostgreSQL falhou: {e}")
        return False

def persistir_csv(timestamp, evento_id, y_pred, y_true, horizonte, cota_atual):
    path = "resultados/predicoes_shadow.csv"
    os.makedirs("resultados", exist_ok=True)
    novo = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["timestamp", "modelo", "versao", "evento_id",
                        "y_true", "y_pred", "horizonte", "cota_atual"])
        w.writerow([timestamp, MODELO, VERSAO, evento_id,
                    y_true, y_pred, horizonte, cota_atual])
    return True

def registrar(
    timestamp,
    evento_id,
    y_pred,
    horizonte,
    cota_atual=None,
    y_true=None,
    ts_observacao=None,
    ts_predicao=None,
    model_version=None,
    features_hash=None,
):
    ok_pg = persistir_postgres(
        timestamp,
        evento_id,
        y_pred,
        y_true,
        horizonte,
        cota_atual,
        ts_observacao=ts_observacao,
        ts_predicao=ts_predicao,
        model_version=model_version,
        features_hash=features_hash,
    )
    ok_csv = persistir_csv(timestamp, evento_id, y_pred, y_true, horizonte, cota_atual)
    status = "PG" if ok_pg else ("CSV" if ok_csv else "FALHA")
    print(f"[{status}] evento={evento_id} y_pred={y_pred:.4f} h={horizonte}")
    return ok_pg or ok_csv

if __name__ == "__main__":
    print("=== TESTE DE PERSISTENCIA (REGRESSAO) ===")
    agora = datetime.now().isoformat()
    testes = [
        ("cron_teste_001", 2.3, "1h", 70.0),
        ("cron_teste_001", 4.1, "3h", 70.0),
        ("cron_teste_001", 6.8, "6h", 70.0),
    ]
    for ev, yp, h, cota in testes:
        registrar(agora, ev, yp, h, cota)
    print("=== FIM ===")
