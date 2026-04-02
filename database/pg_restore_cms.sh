#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

SOURCE_DB="${DB_DATABASE:-$(load_config_value DB_DATABASE)}"
SOURCE_DB="${SOURCE_DB:-portalcms1}"
DB_USER="${DJANGO_USER:-$(load_config_value DJANGO_USER)}"
DB_USER="${DB_USER:-portalcms_django}"
DB_PASS="${DJANGO_PASS:-$(load_config_value DJANGO_PASS)}"
DB_HOST="${DB_HOSTNAME_WRITE:-${DB_HOSTNAME_READ:-$(load_config_value DB_HOSTNAME_WRITE)}}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-$(load_config_value DB_PORT)}"
DB_PORT="${DB_PORT:-5432}"
INPUT=""
TARGET_DB=""
RECREATE_DB=0
VERIFY_AFTER=1
ALLOW_LIVE_TARGET=0
DRY_RUN=0

usage() {
    cat <<EOF
Usage: ./database/pg_restore_cms.sh --input FILE --target-db NAME [options]

Restore a Portal CMS dump into an explicit target database.

Options:
  --input FILE         Dump file to restore (.dump custom format or .sql)
  --target-db NAME     Target database name
  --recreate-db        Drop and recreate target database before restore
  --allow-live-target  Allow target database to match source/live database
  --no-verify          Skip post-restore verification
  --dry-run            Print the resolved restore steps without executing them
  --help               Show this help

Safety:
  - Refuses to restore into the configured source database by default.
  - Intended for clone-first workflows such as portalcms1_clone.

Example:
  ./database/pg_restore_cms.sh \\
    --input backups/portalcms1_pre_versioning_20260331T174604Z.dump \\
    --target-db portalcms1_clone \\
    --recreate-db
EOF
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --input)
            INPUT="$2"
            shift 2
            ;;
        --target-db)
            TARGET_DB="$2"
            shift 2
            ;;
        --recreate-db)
            RECREATE_DB=1
            shift
            ;;
        --allow-live-target)
            ALLOW_LIVE_TARGET=1
            shift
            ;;
        --no-verify)
            VERIFY_AFTER=0
            shift
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

if [[ -z "$INPUT" || -z "$TARGET_DB" ]]; then
    usage
    exit 1
fi

if [[ ! -r "$INPUT" ]]; then
    echo "Input file not readable: $INPUT" >&2
    exit 1
fi

if [[ "$TARGET_DB" == "$SOURCE_DB" && "$ALLOW_LIVE_TARGET" -ne 1 ]]; then
    echo "Refusing to restore into source/live database '${SOURCE_DB}' without --allow-live-target" >&2
    exit 1
fi

export PGPASSWORD="${DB_PASS}"

echo "Preparing restore"
echo "  input:     ${INPUT}"
echo "  source db: ${SOURCE_DB}"
echo "  target db: ${TARGET_DB}"
echo "  host:      ${DB_HOST}:${DB_PORT}"
echo "  recreate:  ${RECREATE_DB}"
echo "  verify:    ${VERIFY_AFTER}"

DROP_CMD=(
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1
    -c "DROP DATABASE IF EXISTS ${TARGET_DB};"
)
CREATE_CMD=(
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1
    -c "CREATE DATABASE ${TARGET_DB} OWNER ${DB_USER};"
)

if [[ "$INPUT" == *.dump ]]; then
    RESTORE_CMD=(
        pg_restore
        -h "$DB_HOST"
        -p "$DB_PORT"
        -U "$DB_USER"
        -d "$TARGET_DB"
        --no-owner
        --no-acl
        -v
        "$INPUT"
    )
else
    RESTORE_CMD=(
        psql
        -h "$DB_HOST"
        -p "$DB_PORT"
        -U "$DB_USER"
        -d "$TARGET_DB"
        -v ON_ERROR_STOP=1
        -f "$INPUT"
    )
fi

VERIFY_CMD=(
    "${ROOT_DIR}/database/verify_db.sh"
)

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run only. Planned steps:"
    if [[ "$RECREATE_DB" -eq 1 ]]; then
        printf '  %q' "${DROP_CMD[@]}"
        printf '\n'
        printf '  %q' "${CREATE_CMD[@]}"
        printf '\n'
    fi
    printf '  %q' "${RESTORE_CMD[@]}"
    printf '\n'
    if [[ "$VERIFY_AFTER" -eq 1 ]]; then
        echo "  DB_DATABASE=${TARGET_DB} DB_HOSTNAME_READ=${DB_HOST} DB_PORT=${DB_PORT} DJANGO_USER=${DB_USER} ${VERIFY_CMD[0]}"
    fi
    exit 0
fi

if [[ "$RECREATE_DB" -eq 1 ]]; then
    echo "Dropping and recreating target database '${TARGET_DB}'"
    "${DROP_CMD[@]}"
    "${CREATE_CMD[@]}"
fi

"${RESTORE_CMD[@]}"

echo "Restore complete into ${TARGET_DB}"

if [[ "$VERIFY_AFTER" -eq 1 ]]; then
    echo "Running verification against ${TARGET_DB}"
    DB_DATABASE="$TARGET_DB" DB_HOSTNAME_READ="$DB_HOST" DB_PORT="$DB_PORT" DJANGO_USER="$DB_USER" \
        "${ROOT_DIR}/database/verify_db.sh"
fi
