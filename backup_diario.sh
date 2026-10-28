#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/oikos/projetos/ARCTURUS_CLIMATIK"
BACKUP_DIR="$ROOT/backup/$(date +%Y%m%d)"
DATABASE="$ROOT/data/arcturus.db"

if ! command -v sqlite3 >/dev/null 2>&1; then
    echo "sqlite3 is required to create a consistent database backup." >&2
    exit 1
fi

if [[ ! -s "$DATABASE" ]]; then
    echo "SQLite database is missing or empty: $DATABASE" >&2
    exit 1
fi

mkdir -p "$BACKUP_DIR/data" "$BACKUP_DIR/resultados"
sqlite3 "$DATABASE" ".timeout 5000" ".backup '$BACKUP_DIR/arcturus.db'"

for relative_path in \
    data/regime_atual.json \
    data/chuva_ensemble_consolidada.json \
    data/simulacao_probabilidade_atual.json \
    data/health_check.json \
    resultados/historico_previsoes.csv
do
    source_path="$ROOT/$relative_path"
    if [[ ! -s "$source_path" ]]; then
        echo "Required backup source is missing or empty: $source_path" >&2
        exit 1
    fi
    cp -- "$source_path" "$BACKUP_DIR/$relative_path"
done

echo "Daily backup completed: $BACKUP_DIR"
