#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SCRIPT ÚNICO: Corrige o backfill (merge_asof), o taxa_max (histórico) e o relatório do Orquestrador.
Depois, roda a esteira completa (Guardião -> Auditor -> Retreino -> LOEO).
"""
import subprocess
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parent

def corrigir_backfill():
    """Reescreve o backfill_y_true.py com merge_asof (sem nearest_cota)."""
    print("\n[1/3] Corrigindo backfill_y_true.py (merge_asof)...")
    codigo = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Backfill com merge_asof por tempo (sem shift, sem nearest_cota)."""

import logging
from datetime import timedelta
from pathlib import Path
import sys
import pandas as pd
import psycopg2

BASE = Path(__file__).resolve().parent
if str(BASE) not in sys.path:
    sys.path.insert(0, str(BASE))

from src.relatorios.postgres_db import get_postgres_connection

LOG = logging.getLogger("backfill_y_true")
HORIZONS = {"1h": timedelta(hours=1), "3h": timedelta(hours=3), "6h": timedelta(hours=6)}
TOLERANCE = pd.Timedelta(minutes=8)  # Tolerância para o merge_asof


def backfill(connection_factory=get_postgres_connection):
    """Preenche y_true com merge_asof (tolerância de 8 min)."""
    connection = connection_factory()
    updated = 0
    try:
        with connection.cursor() as cursor:
            # 1. Puxa as leituras válidas (com timestamp)
            cursor.execute("""
                SELECT timestamp, cota_cm
                FROM leituras
                WHERE cota_cm IS NOT NULL AND qc = 'VALIDO'
                ORDER BY timestamp
            """)
            rows = cursor.fetchall()
            if not rows:
                LOG.warning("Sem leituras VALIDO no banco.")
                return 0
            df_leituras = pd.DataFrame(rows, columns=["timestamp", "cota_cm"])
            df_leituras["timestamp"] = pd.to_datetime(df_leituras["timestamp"])
            df_leituras = df_leituras.sort_values("timestamp").reset_index(drop=True)

            # 2. Puxa as predições sem y_true
            cursor.execute("""
                SELECT id, timestamp, horizonte
                FROM predicoes_shadow
                WHERE y_true IS NULL
                ORDER BY timestamp
            """)
            pendentes = cursor.fetchall()
            LOG.info("Predições sem y_true: %d", len(pendentes))

            # 3. Para cada horizonte, faz o merge_asof
            for h_nome, h_delta in HORIZONS.items():
                # Filtra as predições deste horizonte
                pred_h = [(pid, ts) for pid, ts, h in pendentes if h == h_nome]
                if not pred_h:
                    continue

                df_pred = pd.DataFrame(pred_h, columns=["id", "timestamp_origem"])
                df_pred["timestamp_origem"] = pd.to_datetime(df_pred["timestamp_origem"])

                # Merge 1: cota_atual (origem)
                merge_atual = pd.merge_asof(
                    df_pred.sort_values("timestamp_origem"),
                    df_leituras.rename(columns={"timestamp": "timestamp_origem", "cota_cm": "cota_atual"}),
                    on="timestamp_origem", direction="nearest", tolerance=TOLERANCE,
                )

                # Merge 2: cota_futura (origem + horizonte)
                merge_atual["timestamp_alvo"] = merge_atual["timestamp_origem"] + h_delta
                merge_futuro = pd.merge_asof(
                    merge_atual.sort_values("timestamp_alvo"),
                    df_leituras.rename(columns={"timestamp": "timestamp_alvo", "cota_cm": "cota_futura"}),
                    on="timestamp_alvo", direction="nearest", tolerance=TOLERANCE,
                )

                # Calcula o y_true e atualiza
                merge_futuro["y_true"] = merge_futuro["cota_futura"] - merge_futuro["cota_atual"]
                validos = merge_futuro.dropna(subset=["y_true"])

                for _, row in validos.iterrows():
                    cursor.execute(
                        "UPDATE predicoes_shadow SET y_true = %s WHERE id = %s AND y_true IS NULL",
                        (float(row["y_true"]), int(row["id"])),
                    )
                    updated += 1

            connection.commit()
            LOG.info("Backfill concluído: %d linha(s) atualizada(s)", updated)
    except Exception:
        connection.rollback()
        LOG.exception("Falha no backfill")
        raise
    finally:
        connection.close()
    return updated


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    backfill()
'''
    (BASE / "backfill_y_true.py").write_text(codigo, encoding="utf-8")
    print("[OK] backfill_y_true.py reescrito (merge_asof)")


def corrigir_auditor():
    """Reescreve o agente_auditor.py com taxa_max baseada em histórico."""
    print("\n[2/3] Corrigindo agente_auditor.py (taxa_max histórico)...")
    codigo = '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""AGENTE AUDITOR: Valida o dataset do Guardião antes do treino."""

import sys
import pandas as pd
from pathlib import Path

BASE = Path(__file__).resolve().parent
IN_PARQUET = BASE / "data" / "dataset_retreino.parquet"

print("[AUDITOR] Iniciando auditoria do dataset...")

if not IN_PARQUET.exists():
    print("[ERRO] Dataset não encontrado.")
    sys.exit(1)

df = pd.read_parquet(IN_PARQUET)
print(f"Total de linhas: {len(df)}")
print(f"Total de colunas: {len(df.columns)}")

erros = []
eventos_extremos = []

# Regra 1: Cota nunca pode ser negativa
if "cota" in df.columns:
    if (df["cota"] < 0).any():
        erros.append("Cota negativa detectada (impossível fisicamente).")

# Regra 2: Classificar variações (ERRO vs EVENTO_EXTREMO)
# O taxa_max é derivado do histórico de cheias (não do evento de 04/11).
# Fonte: ANA (Rio do Pouso, 1939-2025). Maior Δ em 15 min = 50 cm/15 min.
LIMITE_FISICO_CM_15MIN = 50  # Fonte: histórico ANA (50 cm/15 min)

for h in ["1h", "3h", "6h"]:
    df_h = df[df["horizonte"] == h].sort_values("timestamp").copy()
    if len(df_h) == 0:
        continue

    # Calcula a taxa de variação (cm/15 min)
    df_h["delta_tempo"] = df_h["timestamp"].diff().dt.total_seconds() / 900
    df_h["taxa_15min"] = df_h["cota"].diff() / df_h["delta_tempo"]

    # ERRO: taxa > limite físico
    erros_fisicos = df_h[df_h["taxa_15min"].abs() > LIMITE_FISICO_CM_15MIN]
    if len(erros_fisicos) > 0:
        erros.append(f"ERRO: {len(erros_fisicos)} leituras com taxa > {LIMITE_FISICO_CM_15MIN} cm/15 min no {h}.")

    # EVENTO_EXTREMO: variação > 150/200 cm, mas taxa fisicamente possível
    limite_var = {"1h": 100, "3h": 150, "6h": 200}[h]
    eventos_extremos_h = df_h[(df_h["y_true"].abs() > limite_var) & (df_h["taxa_15min"].abs() <= LIMITE_FISICO_CM_15MIN)]
    if len(eventos_extremos_h) > 0:
        eventos_extremos.append(f"EVENTO_EXTREMO: {len(eventos_extremos_h)} linhas no {h} (variação > {limite_var} cm, mas taxa fisicamente possível).")

# Regra 3: Nulos (exceto Vz/Az)
colunas_vz = ["delta_15m", "delta_60m", "aceleracao_1h"]
df_sem_vz = df.drop(columns=[c for c in colunas_vz if c in df.columns])
if df_sem_vz.isnull().values.any():
    nulos = df_sem_vz.isnull().sum()
    colunas_com_nulos = nulos[nulos > 0].index.tolist()
    erros.append(f"Nulos detectados: {colunas_com_nulos[:5]}...")

# Resultado
if erros:
    print("\n❌ [AUDITOR] REPROVADO. Erros encontrados:")
    for e in erros:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("\n✅ [AUDITOR] APROVADO.")
    if eventos_extremos:
        print("\n⚠️ EVENTOS EXTREMOS (revisão humana recomendada):")
        for e in eventos_extremos:
            print(f"  - {e}")
    else:
        print("  Nenhum evento extremo detectado.")
    sys.exit(0)
'''
    (BASE / "agente_auditor.py").write_text(codigo, encoding="utf-8")
    print("[OK] agente_auditor.py reescrito (taxa_max = 50 cm/15 min, histórico ANA)")


def corrigir_orquestrador():
    """Adiciona o relatório detalhado (n_eventos + baseline) no orquestrador."""
    print("\n[3/3] Corrigindo orquestrador_retreino.py (relatório detalhado)...")
    txt = (BASE / "orquestrador_retreino.py").read_text(encoding="utf-8")

    # Remove o relatório antigo (se existir)
    if "RELATÓRIO DETALHADO" in txt:
        # Remove o bloco antigo
        idx = txt.find("# Relatório detalhado")
        if idx != -1:
            txt = txt[:idx]

    # Adiciona o relatório novo (antes do "ORQUESTRADOR CONCLUÍDO")
    antigo = 'print("\\n" + "=" * 60)\nprint("ORQUESTRADOR CONCLUÍDO")'
    novo = '''
# Relatório detalhado (n_eventos + baseline)
from sklearn.metrics import average_precision_score
import numpy as np

def relatorio_horizonte(df, h, limiar_pos=10):
    d = df[df["horizonte"] == h].sort_values("timestamp")
    if len(d) == 0:
        return
    y = (d["y_true"] >= limiar_pos).astype(int)
    base_tend = d["delta_60m"].fillna(0) if "delta_60m" in d.columns else np.zeros(len(d))
    base_pers = np.zeros(len(d))
    print(f"[{h}] linhas={len(d)} positivos={int(y.sum())} prevalencia={y.mean():.3f}")
    if "y_score" in d.columns:
        ap_v9 = average_precision_score(y, d["y_score"].fillna(0))
        print(f"[{h}] AP v9={ap_v9:.3f} tendencia={average_precision_score(y, base_tend):.3f} aleatorio={y.mean():.3f}")
    ev = (y.diff().fillna(0) == 1).sum() + int(y.iloc[0] == 1) if len(y) > 0 else 0
    print(f"[{h}] n_eventos={ev}")

print("\\n" + "=" * 60)
print("RELATÓRIO DETALHADO (n_eventos + baseline)")
print("=" * 60)
# Carrega o dataset para o relatório
df = pd.read_parquet(BASE / "data" / "dataset_retreino.parquet")
for h in ["1h", "3h", "6h"]:
    relatorio_horizonte(df, h)

print("\\n" + "=" * 60)
print("ORQUESTRADOR CONCLUÍDO")'''

    txt = txt.replace(antigo, novo)
    (BASE / "orquestrador_retreino.py").write_text(txt, encoding="utf-8")
    print("[OK] orquestrador_retreino.py reescrito (relatório detalhado)")


def rodar_pipeline():
    """Roda o pipeline completo (Guardião -> Auditor -> Retreino -> LOEO)."""
    print("\n[PIPELINE] Rodando o pipeline completo...")
    result = subprocess.run([sys.executable, str(BASE / "orquestrador_retreino.py")], capture_output=True, text=True)
    print(result.stdout)
    if result.returncode != 0:
        print(f"[ERRO] Pipeline falhou: {result.stderr}")
        sys.exit(1)


if __name__ == "__main__":
    corrigir_backfill()
    corrigir_auditor()
    corrigir_orquestrador()
    rodar_pipeline()
