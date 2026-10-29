#!/usr/bin/env bash
set -euo pipefail

workspace_root="/home/oikos/projetos/ARCTURUS_CLIMATIK"
env_file="$workspace_root/.env"
if [[ ! -r "$env_file" ]]; then
    echo "Nylas environment file is missing or unreadable: $env_file" >&2
    exit 1
fi

set -a
source "$env_file"
set +a

if [[ -z "${NYLAS_API_KEY:-}" || -z "${NYLAS_GRANT_ID:-}" || -z "${NYLAS_FILE_STORE_PASSPHRASE:-}" ]]; then
    echo "NYLAS_API_KEY, NYLAS_GRANT_ID, and NYLAS_FILE_STORE_PASSPHRASE must be configured in .env." >&2
    exit 1
fi

cd "$workspace_root"
exec /home/oikos/.config/nylas/bin/nylas mcp serve
