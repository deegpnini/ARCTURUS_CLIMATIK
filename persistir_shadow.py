#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, csv
from datetime import datetime

DB_URL = os.environ.get("DATABASE_URL", "postgresql:///arcturus")
MODELO = "LightGBM_v2"
VERSAO = "2.0.0"

def persistir_postgres(timestamp, evento_id, y_true, y_score, threshold, horizonte):
    try:
        import psycopg2
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        cur.execute("""
            INSERT INTO predicoes_shadow
            (timestamp, modelo, versao, evento_id, y_true, y_score, threshold, horizonte)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
        """, (timestamp, MODELO, VERSAO, evento_id, y_true, y_score, threshold, horizonte))
        conn.commit()
        cur.close()
        conn.close()
        return True
    except Exception as e:
        print(f"[AVISO] PostgreSQL falhou: {e}")
        return False

def persistir_csv(timestamp, evento_id, y_true, y_score, threshold, horizonte):
    path = "resultados/predicoes_shadow.csv"
    os.makedirs("resultados", exist_ok=True)
    novo = not os.path.exists(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        if novo:
            w.writerow(["timestamp", "modelo", "versao", "evento_id",
                        "y_true", "y_score", "threshold", "horizonte"])
        w.writerow([timestamp, MODELO, VERSAO, evento_id,
                    y_true, y_score, threshold, horizonte])
    return True

def registrar(timestamp, evento_id, y_true, y_score, threshold, horizonte):
    ok_pg = persistir_postgres(timestamp, evento_id, y_true, y_score, threshold, horizonte)
    ok_csv = persistir_csv(timestamp, evento_id, y_true, y_score, threshold, horizonte)
    status = "PG" if ok_pg else ("CSV" if ok_csv else "FALHA")
    print(f"[{status}] evento={evento_id} y_true={y_true} y_score={y_score:.4f} threshold={threshold} h={horizonte}")
    return ok_pg or ok_csv

if __name__ == "__main__":
    print("=== TESTE DE PERSISTENCIA — MODO SOMBRA ===")
    agora = datetime.now().isoformat()
    testes = [
        ("evento_teste_001", 1, 0.72, 0.50, "1h"),
        ("evento_teste_001", 0, 0.31, 0.50, "3h"),
        ("evento_teste_001", 1, 0.18, 0.50, "6h"),
    ]
    for ev, yt, ys, th, h in testes:
        registrar(agora, ev, yt, ys, th, h)
    print("=== FIM DO TESTE ===")
