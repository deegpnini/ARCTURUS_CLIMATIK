#!/usr/bin/env bash
set -euo pipefail

if (( EUID == 0 )); then
    SUDO=()
else
    SUDO=(sudo)
fi

run_as_postgres() {
    if (( EUID == 0 )); then
        runuser -u postgres -- "$@"
    else
        sudo -u postgres "$@"
    fi
}

"${SUDO[@]}" apt-get update
"${SUDO[@]}" apt-get install -y postgresql postgresql-contrib postgis sqlite3
"${SUDO[@]}" service postgresql start

if [[ "$(run_as_postgres psql -tAc "SELECT 1 FROM pg_roles WHERE rolname = 'oikos'")" != "1" ]]; then
    run_as_postgres createuser --login oikos
fi

if [[ "$(run_as_postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'arcturus'")" != "1" ]]; then
    run_as_postgres createdb --owner=oikos arcturus
fi

run_as_postgres psql -v ON_ERROR_STOP=1 -d arcturus -c "CREATE EXTENSION IF NOT EXISTS postgis;"

printf 'PostgreSQL database arcturus and PostGIS are ready for role oikos.\n'
