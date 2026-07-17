#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_config_value() {
    local key="$1"
    local config_file="${APP_CONFIG:-}"

    if [[ -z "$config_file" ]]; then
        if [[ -f "${ROOT_DIR}/portal.conf.dev.json" ]]; then
            config_file="${ROOT_DIR}/portal.conf.dev.json"
        elif [[ -f "${ROOT_DIR}/portal.conf.json" ]]; then
            config_file="${ROOT_DIR}/portal.conf.json"
        elif [[ -f "${ROOT_DIR}/portalcms.conf.dev.json" ]]; then
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
SOURCE_DB="${SOURCE_DB:-portal1}"
DB_USER="${DJANGO_USER:-$(load_config_value DJANGO_USER)}"
DB_USER="${DB_USER:-portal_django}"
DB_PASS="${DJANGO_PASS:-$(load_config_value DJANGO_PASS)}"
DB_OWNER="${DB_OWNER:-$(load_config_value DB_OWNER)}"
DB_SCHEMA="${DB_SCHEMA:-$(load_config_value DB_SCHEMA)}"
DB_HOST="${DB_HOSTNAME_WRITE:-${DB_HOSTNAME_READ:-$(load_config_value DB_HOSTNAME_WRITE)}}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-$(load_config_value DB_PORT)}"
DB_PORT="${DB_PORT:-5432}"
DB_SSLMODE="${DB_SSLMODE:-$(load_config_value DB_SSLMODE)}"
DB_SSLROOTCERT="${DB_SSLROOTCERT:-$(load_config_value DB_SSLROOTCERT)}"
DB_SSLCERT="${DB_SSLCERT:-$(load_config_value DB_SSLCERT)}"
DB_SSLKEY="${DB_SSLKEY:-$(load_config_value DB_SSLKEY)}"
INPUT=""
TARGET_DB=""
RECREATE_DB=0
VERIFY_AFTER=1
ALLOW_LIVE_TARGET=0
SKIP_SCHEMA_CREATE=0
CLEAN_RESTORE=0
DRY_RUN=0
TEMP_LIST_FILE=""

cleanup() {
    if [[ -n "$TEMP_LIST_FILE" && -f "$TEMP_LIST_FILE" ]]; then
        rm -f "$TEMP_LIST_FILE"
    fi
}

trap cleanup EXIT

usage() {
    cat <<EOF
Usage: ./database/pg_restore_portal.sh --input FILE --target-db NAME [options]

Restore a Portal CMS dump into an explicit target database.

Options:
  --input FILE         Dump file to restore (.dump custom format or .sql)
  --target-db NAME     Target database name
  --recreate-db        Drop and recreate target database before restore
  --allow-live-target  Allow target database to match source/live database
  --skip-schema-create Exclude CREATE SCHEMA for the app schema from custom-format restores
  --clean-restore      Drop and recreate all objects within the target database
                       before restore; implies --skip-schema-create (schema must
                       already exist in the target database, created by an admin)
  --no-verify          Skip post-restore verification
  --dry-run            Print the resolved restore steps without executing them
  --help               Show this help

Safety:
  - Refuses to restore into the configured source database by default.
  - Intended for clone-first workflows such as portal1_clone.

Examples:
  ./database/pg_restore_portal.sh \\
    --input backups/portalcms1_pre_versioning_20260331T174604Z.dump \\
    --target-db portal1_clone \\
    --recreate-db

  ./database/pg_restore_portal.sh \\
    --input database/dumps/portal1_full_<timestamp>.dump \\
    --target-db portal_dev \\
    --clean-restore
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
        --skip-schema-create)
            SKIP_SCHEMA_CREATE=1
            shift
            ;;
        --clean-restore)
            CLEAN_RESTORE=1
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
if [[ -n "${DB_SSLMODE}" ]]; then
    export PGSSLMODE="${DB_SSLMODE}"
fi
if [[ -n "${DB_SSLROOTCERT}" ]]; then
    export PGSSLROOTCERT="${DB_SSLROOTCERT}"
fi
if [[ -n "${DB_SSLCERT}" ]]; then
    export PGSSLCERT="${DB_SSLCERT}"
fi
if [[ -n "${DB_SSLKEY}" ]]; then
    export PGSSLKEY="${DB_SSLKEY}"
fi

echo "Preparing restore"
echo "  input:     ${INPUT}"
echo "  source db: ${SOURCE_DB}"
echo "  target db: ${TARGET_DB}"
echo "  host:      ${DB_HOST}:${DB_PORT}"
if [[ -n "${DB_SSLMODE}" ]]; then
    echo "  sslmode:   ${DB_SSLMODE}"
fi
echo "  recreate:  ${RECREATE_DB}"
echo "  skip schema create: ${SKIP_SCHEMA_CREATE}"
echo "  clean restore: ${CLEAN_RESTORE}"
echo "  verify:    ${VERIFY_AFTER}"

DROP_CMD=(
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1
    -c "DROP DATABASE IF EXISTS ${TARGET_DB};"
)
CREATE_CMD=(
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d postgres -v ON_ERROR_STOP=1
    -c "CREATE DATABASE ${TARGET_DB} OWNER ${DB_OWNER:-$DB_USER};"
)

RESTORE_SCHEMA="${DB_SCHEMA:-$DB_USER}"
if [[ "$INPUT" == *.dump ]]; then
    if [[ "$SKIP_SCHEMA_CREATE" -eq 1 || "$CLEAN_RESTORE" -eq 1 ]]; then
        TEMP_LIST_FILE="$(mktemp)"
        pg_restore -l "$INPUT" | awk -v schema="$RESTORE_SCHEMA" '
            index($0, " SCHEMA - " schema " ") == 0 { print }
        ' > "$TEMP_LIST_FILE"
    fi

    RESTORE_CMD=(
        pg_restore
        -h "$DB_HOST"
        -p "$DB_PORT"
        -U "$DB_USER"
        -d "$TARGET_DB"
        --no-owner
        --no-acl
        -v
    )
    if [[ "$CLEAN_RESTORE" -eq 1 ]]; then
        RESTORE_CMD+=(--clean --if-exists)
    fi
    if [[ -n "$TEMP_LIST_FILE" ]]; then
        RESTORE_CMD+=(
            --use-list="$TEMP_LIST_FILE"
        )
    fi
    RESTORE_CMD+=(
        "$INPUT"
    )
else
    if [[ "$SKIP_SCHEMA_CREATE" -eq 1 || "$CLEAN_RESTORE" -eq 1 ]]; then
        echo "--skip-schema-create and --clean-restore are only supported for custom-format .dump inputs" >&2
        exit 1
    fi
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
    if [[ -n "$TEMP_LIST_FILE" ]]; then
        if [[ "$CLEAN_RESTORE" -eq 1 ]]; then
            printf '  %q' pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" --clean --if-exists --no-owner --no-acl -v --use-list="<generated temp list>" "$INPUT"
        else
            printf '  %q' pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" --no-owner --no-acl -v --use-list="<generated temp list>" "$INPUT"
        fi
        printf '\n'
    else
        printf '  %q' "${RESTORE_CMD[@]}"
        printf '\n'
    fi
    if [[ "$VERIFY_AFTER" -eq 1 ]]; then
        echo "  DB_DATABASE=${TARGET_DB} DB_HOSTNAME_READ=${DB_HOST} DB_PORT=${DB_PORT} DJANGO_USER=${DB_USER} DB_SCHEMA=${DB_SCHEMA} DB_SSLMODE=${DB_SSLMODE} ${VERIFY_CMD[0]}"
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
    DB_DATABASE="$TARGET_DB" DB_HOSTNAME_READ="$DB_HOST" DB_PORT="$DB_PORT" DJANGO_USER="$DB_USER" DB_SCHEMA="$DB_SCHEMA" DB_SSLMODE="$DB_SSLMODE" \
        "${ROOT_DIR}/database/verify_db.sh"
fi
