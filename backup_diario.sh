#!/usr/bin/env bash
set -euo pipefail

ROOT="/home/oikos/projetos/ARCTURUS_CLIMATIK"
BACKUP_DIR="$ROOT/backup/$(date +%Y%m%d)"
DATABASE="$ROOT/data/arcturus.db"

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "pg_dump is required to back up the PostgreSQL database." >&2
    exit 1
fi

export PGDATABASE="${ARCTURUS_DB_NAME:-arcturus}"
export PGUSER="${ARCTURUS_DB_USER:-oikos}"
if [[ -n "${ARCTURUS_DB_HOST:-}" ]]; then
    export PGHOST="$ARCTURUS_DB_HOST"
fi
if [[ -n "${ARCTURUS_DB_PORT:-}" ]]; then
    export PGPORT="$ARCTURUS_DB_PORT"
fi
if [[ -n "${ARCTURUS_DB_PASSWORD:-}" ]]; then
    export PGPASSWORD="$ARCTURUS_DB_PASSWORD"
fi

mkdir -p "$BACKUP_DIR/data" "$BACKUP_DIR/resultados"
pg_dump --format=custom --file="$BACKUP_DIR/arcturus.dump"
if [[ -s "$DATABASE" ]]; then
    if ! command -v sqlite3 >/dev/null 2>&1; then
        echo "sqlite3 is required to preserve the legacy SQLite snapshot." >&2
        exit 1
    fi
    sqlite3 "$DATABASE" ".timeout 5000" ".backup '$BACKUP_DIR/arcturus.db'"
fi

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
