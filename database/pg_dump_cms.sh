#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DUMP_DIR="${ROOT_DIR}/database/dumps"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

load_config_value() {
    local key="$1"
    local config_file="${APP_CONFIG:-}"

    if [[ -z "$config_file" ]]; then
        if [[ -f "${ROOT_DIR}/portalcms.conf.dev.json" ]]; then
            config_file="${ROOT_DIR}/portalcms.conf.dev.json"
        elif [[ -f "${ROOT_DIR}/portalcms.conf.json" ]]; then
            config_file="${ROOT_DIR}/portalcms.conf.json"
        fi
    fi

    if [[ -n "$config_file" && -f "$config_file" ]]; then
        python3 - "$config_file" "$key" <<'PY'
import json
import sys

config_path, key = sys.argv[1], sys.argv[2]
with open(config_path, "r", encoding="utf-8") as fh:
    value = json.load(fh).get(key, "")
if isinstance(value, list):
    print(",".join(str(v) for v in value))
elif value is None:
    print("")
else:
    print(value)
PY
    fi
}

DB_NAME="${DB_DATABASE:-$(load_config_value DB_DATABASE)}"
DB_NAME="${DB_NAME:-portalcms1}"
DB_USER="${DJANGO_USER:-$(load_config_value DJANGO_USER)}"
DB_USER="${DB_USER:-portalcms_django}"
DB_PASS="${DJANGO_PASS:-$(load_config_value DJANGO_PASS)}"
DB_HOST="${DB_HOSTNAME_READ:-$(load_config_value DB_HOSTNAME_READ)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-$(load_config_value DB_PORT)}"
DB_PORT="${DB_PORT:-5432}"
FORMAT="custom"
OUTPUT=""
DRY_RUN=0

usage() {
    cat <<EOF
Usage: ./database/pg_dump_cms.sh [options]

Create a safe PostgreSQL dump of the configured Portal CMS database.

Options:
  --source-db NAME     Source database name (default: ${DB_NAME})
  --output PATH        Explicit output path
  --format TYPE        Dump format: custom or sql (default: custom)
  --dry-run            Print the resolved dump command without executing it
  --help               Show this help

Examples:
  ./database/pg_dump_cms.sh
  ./database/pg_dump_cms.sh --source-db portalcms1 --format sql
  ./database/pg_dump_cms.sh --output database/dumps/portalcms1_clone_seed.dump
  ./database/pg_dump_cms.sh --dry-run
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --source-db)
            DB_NAME="$2"
            shift 2
            ;;
        --output)
            OUTPUT="$2"
            shift 2
            ;;
        --format)
            FORMAT="$2"
            shift 2
            ;;
        --dry-run)
            DRY_RUN=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "Unknown argument: $1" >&2
            usage
            exit 1
            ;;
    esac
done

if [[ "$FORMAT" != "custom" && "$FORMAT" != "sql" ]]; then
    echo "Unsupported format: $FORMAT" >&2
    exit 1
fi

mkdir -p "$DUMP_DIR"

if [[ -z "$OUTPUT" ]]; then
    if [[ "$FORMAT" == "custom" ]]; then
        OUTPUT="${DUMP_DIR}/${DB_NAME}_full_${TIMESTAMP}.dump"
    else
        OUTPUT="${DUMP_DIR}/${DB_NAME}_full_${TIMESTAMP}.sql"
    fi
fi

echo "Preparing dump"
echo "  database: ${DB_NAME}"
echo "  user:     ${DB_USER}"
echo "  host:     ${DB_HOST}:${DB_PORT}"
echo "  format:   ${FORMAT}"
echo "  output:   ${OUTPUT}"

export PGPASSWORD="${DB_PASS}"

if [[ "$FORMAT" == "custom" ]]; then
    CMD=(
        pg_dump
        -h "$DB_HOST"
        -p "$DB_PORT"
        -U "$DB_USER"
        -d "$DB_NAME"
        -F c
        -b
        -v
        -f "$OUTPUT"
    )
else
    CMD=(
        pg_dump
        -h "$DB_HOST"
        -p "$DB_PORT"
        -U "$DB_USER"
        -d "$DB_NAME"
        --clean
        --if-exists
        --create
        -v
        -f "$OUTPUT"
    )
fi

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run only. Command:"
    printf '  %q' "${CMD[@]}"
    printf '\n'
    exit 0
fi

if [[ "$FORMAT" == "custom" ]]; then
    "${CMD[@]}"
else
    "${CMD[@]}"
fi

echo "Dump complete: ${OUTPUT}"
