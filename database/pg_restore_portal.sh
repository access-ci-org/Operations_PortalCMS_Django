#!/bin/bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ -z "${APP_CONFIG:-}" ]]; then
    DEPLOYED_APP_CONFIG="${ROOT_DIR}/../../conf/portal.conf"
    if [[ -f "$DEPLOYED_APP_CONFIG" ]]; then
        APP_CONFIG="$DEPLOYED_APP_CONFIG"
        export APP_CONFIG
    fi
fi

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

SOURCE_DB="${RESTORE_SOURCE_DB:-portal1}"
DB_USER="${DJANGO_USER:-$(load_config_value DJANGO_USER)}"
DB_USER="${DB_USER:-portal_django}"
DB_PASS="${DJANGO_PASS:-$(load_config_value DJANGO_PASS)}"
DB_SCHEMA="${DB_SCHEMA:-$(load_config_value DB_SCHEMA)}"
DB_OWNER="${DB_OWNER:-$(load_config_value DB_OWNER)}"
DB_OWNER="${DB_OWNER:-portal_owner}"
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
INPUT_FORMAT=""
ADMIN_USER="${DB_ADMIN_USER:-}"
TARGET_OWNER_OVERRIDE=""
MAINTENANCE_USER="${DB_MAINTENANCE_USER:-$DB_OWNER}"
MAINTENANCE_USER_EXPLICIT=0
MAINTENANCE_GRANT_ADDED=0
RESTORE_SCHEMA="${DB_SCHEMA:-$DB_USER}"

cleanup() {
    local exit_code=$?
    local cleanup_failed=0

    trap - EXIT
    if [[ "$MAINTENANCE_GRANT_ADDED" -eq 1 ]]; then
        if ! run_maintenance_command \
            psql -X -h "$DB_HOST" -p "$DB_PORT" -U "$MAINTENANCE_USER" \
            -d "$TARGET_DB" -w -v ON_ERROR_STOP=1 \
            -c "REVOKE CREATE ON DATABASE \"${TARGET_DB}\" FROM \"${DB_USER}\";"; then
            echo "WARNING: failed to revoke temporary CREATE privilege from '${DB_USER}' on '${TARGET_DB}'." >&2
            echo "An authorized operator must review and revoke it manually." >&2
            cleanup_failed=1
        fi
    fi
    if [[ -n "$TEMP_LIST_FILE" && -f "$TEMP_LIST_FILE" ]]; then
        rm -f "$TEMP_LIST_FILE"
    fi
    if [[ "$exit_code" -eq 0 && "$cleanup_failed" -eq 1 ]]; then
        exit_code=1
    fi
    exit "$exit_code"
}

trap cleanup EXIT

detect_input_format() {
    local input_file="$1"
    local magic

    magic=$(LC_ALL=C head -c 5 "$input_file")
    if [[ "$magic" == "PGDMP" ]]; then
        printf 'custom\n'
        return
    fi

    if LC_ALL=C grep -Iq '' "$input_file"; then
        printf 'sql\n'
        return
    fi

    echo "Unsupported or unrecognized dump format: $input_file" >&2
    return 1
}

validate_plain_sql_target_safety() {
    local input_file="$1"

    if LC_ALL=C grep -Eiq '^[[:space:]]*\\(connect|c)([[:space:]]|$)' "$input_file"; then
        echo "Refusing plain SQL dump containing a psql database connection command." >&2
        echo "It could switch away from the explicit target database '${TARGET_DB}'." >&2
        return 1
    fi

    if LC_ALL=C grep -Eiq '^[[:space:]]*(CREATE|DROP|ALTER)[[:space:]]+DATABASE([[:space:]]|;)' "$input_file"; then
        echo "Refusing plain SQL dump containing database-level DDL." >&2
        echo "It could create, drop, or alter a database other than '${TARGET_DB}'." >&2
        return 1
    fi
}

validate_plain_sql_schema_restore() {
    local input_file="$1"
    local schema_pattern

    schema_pattern="^[[:space:]]*CREATE[[:space:]]+SCHEMA([[:space:]]+IF[[:space:]]+NOT[[:space:]]+EXISTS)?[[:space:]]+\"?${RESTORE_SCHEMA}\"?([[:space:]]|;)"
    if ! LC_ALL=C grep -Eiq "$schema_pattern" "$input_file"; then
        echo "Plain SQL clean restore requires the dump to create schema '${RESTORE_SCHEMA}'." >&2
        echo "The existing schema is removed before restore, so a schema-complete dump is required." >&2
        return 1
    fi
}

validate_identifier() {
    local value="$1"
    local label="$2"

    if [[ ! "$value" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]]; then
        echo "Invalid ${label}: '${value}'" >&2
        echo "Use only letters, numbers, and underscores, beginning with a letter or underscore." >&2
        return 1
    fi
}

run_admin_command() {
    if [[ -n "${PGPASSFILE:-}" ]]; then
        env -u PGPASSWORD "$@"
    else
        "$@"
    fi
}

run_maintenance_command() {
    if [[ -n "${PGPASSFILE:-}" ]]; then
        env -u PGPASSWORD "$@"
    else
        "$@"
    fi
}

admin_query() {
    run_admin_command \
        psql -X -h "$DB_HOST" -p "$DB_PORT" -U "$ADMIN_USER" -d postgres \
        -w -v ON_ERROR_STOP=1 -t -A "$@"
}

maintenance_query() {
    run_maintenance_command \
        psql -X -h "$DB_HOST" -p "$DB_PORT" -U "$MAINTENANCE_USER" -d "$TARGET_DB" \
        -w -v ON_ERROR_STOP=1 -t -A "$@"
}

prepare_plain_sql_clean_restore() {
    local database_owner
    local schema_owner
    local application_role_exists
    local active_connections
    local application_can_create

    database_owner=$(maintenance_query -c "
SELECT pg_get_userbyid(datdba)
FROM pg_database
WHERE datname = current_database();
")
    if [[ "$database_owner" != "$MAINTENANCE_USER" ]]; then
        echo "Maintenance role '${MAINTENANCE_USER}' does not own target database '${TARGET_DB}'." >&2
        echo "Use the target database owner for the existing-database clean restore." >&2
        return 1
    fi

    application_role_exists=$(maintenance_query -c "
SELECT count(*)
FROM pg_roles
WHERE rolname = '${DB_USER}';
")
    if [[ "$application_role_exists" != "1" ]]; then
        echo "Application database role '${DB_USER}' does not exist." >&2
        return 1
    fi

    active_connections=$(maintenance_query -c "
SELECT count(*)
FROM pg_stat_activity
WHERE datname = current_database()
  AND backend_type = 'client backend'
  AND pid <> pg_backend_pid();
")
    if [[ "$active_connections" != "0" ]]; then
        echo "Target database '${TARGET_DB}' has ${active_connections} active connection(s)." >&2
        echo "Stop its applications and disconnect users before retrying." >&2
        return 1
    fi

    schema_owner=$(maintenance_query -c "
SELECT pg_get_userbyid(nspowner)
FROM pg_namespace
WHERE nspname = '${RESTORE_SCHEMA}';
")
    if [[ -n "$schema_owner" && "$schema_owner" != "$MAINTENANCE_USER" && "$schema_owner" != "$DB_USER" ]]; then
        echo "Schema '${RESTORE_SCHEMA}' is owned by unexpected role '${schema_owner}'." >&2
        echo "Expected '${MAINTENANCE_USER}' or '${DB_USER}'; refusing destructive cleanup." >&2
        return 1
    fi

    application_can_create=$(maintenance_query -c "
SELECT CASE
    WHEN has_database_privilege('${DB_USER}', current_database(), 'CREATE') THEN 't'
    ELSE 'f'
END;
")
    if [[ "$application_can_create" != "t" ]]; then
        maintenance_query -c "
GRANT CREATE ON DATABASE \"${TARGET_DB}\" TO \"${DB_USER}\";
" >/dev/null
        MAINTENANCE_GRANT_ADDED=1
    fi

    if [[ "$schema_owner" == "$MAINTENANCE_USER" ]]; then
        echo "Removing maintenance-owned schema '${RESTORE_SCHEMA}' from '${TARGET_DB}'"
        echo "  A restore failure after this point can leave the non-production target without this schema."
        maintenance_query -c "
DROP SCHEMA \"${RESTORE_SCHEMA}\" CASCADE;
" >/dev/null
    fi
}

recreate_target_database() {
    local admin_can_create
    local source_metadata
    local source_encoding
    local source_collate
    local source_ctype
    local existing_owner
    local target_owner
    local owner_exists
    local active_connections

    admin_can_create=$(admin_query -c "
SELECT CASE WHEN rolcreatedb OR rolsuper THEN 't' ELSE 'f' END
FROM pg_roles
WHERE rolname = current_user;
")
    if [[ "$admin_can_create" != "t" ]]; then
        echo "Administrative role '${ADMIN_USER}' does not have CREATEDB privilege." >&2
        return 1
    fi

    source_metadata=$(admin_query -F '|' -c "
SELECT pg_encoding_to_char(encoding), datcollate, datctype
FROM pg_database
WHERE datname = '${SOURCE_DB}';
")
    if [[ -z "$source_metadata" ]]; then
        echo "Source database metadata not found for '${SOURCE_DB}'." >&2
        return 1
    fi
    IFS='|' read -r source_encoding source_collate source_ctype <<< "$source_metadata"
    if [[ -z "$source_encoding" || -z "$source_collate" || -z "$source_ctype" ]]; then
        echo "Source database metadata is incomplete for '${SOURCE_DB}'." >&2
        return 1
    fi

    existing_owner=$(admin_query -c "
SELECT pg_get_userbyid(datdba)
FROM pg_database
WHERE datname = '${TARGET_DB}';
")
    if [[ -n "$existing_owner" ]]; then
        target_owner="$existing_owner"
        active_connections=$(admin_query -c "
SELECT count(*)
FROM pg_stat_activity
WHERE datname = '${TARGET_DB}'
  AND backend_type = 'client backend';
")
        if [[ "$active_connections" != "0" ]]; then
            echo "Target database '${TARGET_DB}' has ${active_connections} active connection(s)." >&2
            echo "Stop its applications and disconnect users before retrying." >&2
            return 1
        fi
    else
        target_owner="$TARGET_OWNER_OVERRIDE"
        if [[ -z "$target_owner" ]]; then
            echo "Target database '${TARGET_DB}' does not exist; --owner is required." >&2
            return 1
        fi
    fi

    validate_identifier "$target_owner" "target database owner"
    owner_exists=$(admin_query -c "
SELECT count(*)
FROM pg_roles
WHERE rolname = '${target_owner}';
")
    if [[ "$owner_exists" != "1" ]]; then
        echo "Target database owner role '${target_owner}' does not exist." >&2
        return 1
    fi

    echo "Recreating target database '${TARGET_DB}'"
    echo "  admin user: ${ADMIN_USER}"
    echo "  owner:      ${target_owner}"
    echo "  encoding:   ${source_encoding}"
    echo "  collation:  ${source_collate}"
    echo "  ctype:      ${source_ctype}"

    if [[ -n "$existing_owner" ]]; then
        run_admin_command \
            dropdb -h "$DB_HOST" -p "$DB_PORT" -U "$ADMIN_USER" \
            -w --maintenance-db=postgres "$TARGET_DB"
    fi

    run_admin_command \
        createdb -h "$DB_HOST" -p "$DB_PORT" -U "$ADMIN_USER" \
        -w \
        --maintenance-db=postgres \
        --template=template0 \
        --owner="$target_owner" \
        --encoding="$source_encoding" \
        --lc-collate="$source_collate" \
        --lc-ctype="$source_ctype" \
        "$TARGET_DB"
}

usage() {
    cat <<EOF
Usage: ./database/pg_restore_portal.sh --input FILE --target-db NAME [options]

Restore a Portal CMS dump into an explicit target database.

Options:
  --input FILE         Dump file to restore (.dump custom format or .sql)
  --source-db NAME     Database represented by the dump (default: portal1)
  --target-db NAME     Target database name
  --recreate-db        Drop and recreate target database before restore
  --admin-user NAME    Administrative role used only with --recreate-db
                       Credentials are resolved by libpq; prefer PGPASSFILE
  --owner NAME         Owner for a newly created target; ignored when an
                       existing target owner can be preserved
  --maintenance-user NAME
                       Target database owner used to prepare an existing
                       database for a plain-SQL --clean-restore
                       (default: DB_OWNER from config, then portal_owner)
  --allow-live-target  Allow target database to match source/live database
  --skip-schema-create Exclude CREATE SCHEMA for the app schema from custom-format restores
  --clean-restore      Drop and recreate all objects within the target database
                       before restore. Custom archives preserve the existing
                       schema; plain SQL replaces the application schema.
  --no-verify          Skip post-restore verification
  --dry-run            Print the resolved restore steps without executing them
  --help               Show this help

Safety:
  - Refuses to restore into the explicit source database by default.
  - Never permits --recreate-db when target and source database names match.
  - Plain SQL requires --clean-restore or --recreate-db to avoid conflicts.
  - Plain-SQL clean restore keeps the target database but replaces its
    application schema; it rejects database DDL and psql reconnect commands.

Examples:
  PGPASSFILE=/path/to/operator-managed.pgpass \\
  ./database/pg_restore_portal.sh \\
    --input database/dumps/django.portal1.dump.<epoch>.sql \\
    --source-db portal1 \\
    --target-db portal_dev \\
    --clean-restore

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
        --source-db)
            SOURCE_DB="$2"
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
        --admin-user)
            ADMIN_USER="$2"
            shift 2
            ;;
        --owner)
            TARGET_OWNER_OVERRIDE="$2"
            shift 2
            ;;
        --maintenance-user)
            MAINTENANCE_USER="$2"
            MAINTENANCE_USER_EXPLICIT=1
            shift 2
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

validate_identifier "$SOURCE_DB" "source database name"
validate_identifier "$TARGET_DB" "target database name"
validate_identifier "$DB_USER" "application database user"
validate_identifier "$DB_OWNER" "configured database owner"
validate_identifier "$RESTORE_SCHEMA" "application database schema"

if [[ "$TARGET_DB" == "$SOURCE_DB" ]]; then
    if [[ "$RECREATE_DB" -eq 1 ]]; then
        echo "Refusing to recreate source/live database '${SOURCE_DB}'." >&2
        exit 1
    elif [[ "$ALLOW_LIVE_TARGET" -ne 1 ]]; then
        echo "Refusing to restore into source/live database '${SOURCE_DB}' without --allow-live-target" >&2
        exit 1
    fi
fi

if [[ "$RECREATE_DB" -eq 1 && "$CLEAN_RESTORE" -eq 1 ]]; then
    echo "--recreate-db and --clean-restore cannot be combined." >&2
    exit 1
fi

if [[ "$RECREATE_DB" -eq 1 ]]; then
    if [[ -z "$ADMIN_USER" ]]; then
        echo "--admin-user is required with --recreate-db." >&2
        echo "Supply its credentials through libpq, preferably with PGPASSFILE." >&2
        exit 1
    fi
    validate_identifier "$ADMIN_USER" "administrative database user"
    if [[ -n "$TARGET_OWNER_OVERRIDE" ]]; then
        validate_identifier "$TARGET_OWNER_OVERRIDE" "target database owner"
    fi
elif [[ -n "$ADMIN_USER" || -n "$TARGET_OWNER_OVERRIDE" ]]; then
    echo "--admin-user and --owner are only valid with --recreate-db." >&2
    exit 1
fi

INPUT_FORMAT="$(detect_input_format "$INPUT")"

if [[ "$INPUT_FORMAT" == "sql" ]]; then
    validate_plain_sql_target_safety "$INPUT"
    if [[ "$RECREATE_DB" -ne 1 && "$CLEAN_RESTORE" -ne 1 ]]; then
        echo "Plain SQL restores require --clean-restore or --recreate-db to prevent conflicts." >&2
        exit 1
    fi
    if [[ "$SKIP_SCHEMA_CREATE" -eq 1 ]]; then
        echo "--skip-schema-create is only supported for custom-format dumps." >&2
        exit 1
    fi
    if [[ "$CLEAN_RESTORE" -eq 1 ]]; then
        validate_identifier "$MAINTENANCE_USER" "maintenance database user"
        validate_plain_sql_schema_restore "$INPUT"
    elif [[ "$MAINTENANCE_USER_EXPLICIT" -eq 1 ]]; then
        echo "--maintenance-user is only used for a plain-SQL --clean-restore." >&2
        exit 1
    fi
elif [[ "$MAINTENANCE_USER_EXPLICIT" -eq 1 ]]; then
    echo "--maintenance-user is only used for a plain-SQL --clean-restore." >&2
    exit 1
fi

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
echo "  format:    ${INPUT_FORMAT}"
echo "  host:      ${DB_HOST}:${DB_PORT}"
if [[ -n "${DB_SSLMODE}" ]]; then
    echo "  sslmode:   ${DB_SSLMODE}"
fi
echo "  recreate:  ${RECREATE_DB}"
if [[ "$RECREATE_DB" -eq 1 ]]; then
    echo "  admin user: ${ADMIN_USER}"
fi
if [[ "$INPUT_FORMAT" == "sql" && "$CLEAN_RESTORE" -eq 1 ]]; then
    echo "  maintenance user: ${MAINTENANCE_USER}"
fi
echo "  skip schema create: ${SKIP_SCHEMA_CREATE}"
echo "  clean restore: ${CLEAN_RESTORE}"
echo "  verify:    ${VERIFY_AFTER}"

if [[ "$INPUT_FORMAT" == "custom" ]]; then
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
        --no-privileges
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
    RESTORE_CMD=(
        psql
        -X
        -h "$DB_HOST"
        -p "$DB_PORT"
        -U "$DB_USER"
        -d "$TARGET_DB"
        -v ON_ERROR_STOP=1
        --single-transaction
        -c "DROP SCHEMA IF EXISTS \"${RESTORE_SCHEMA}\" CASCADE;"
        -f "$INPUT"
    )
fi

VERIFY_CMD=(
    "${ROOT_DIR}/database/verify_db.sh"
)

if [[ "$DRY_RUN" -eq 1 ]]; then
    echo "Dry run only. Planned steps:"
    if [[ "$RECREATE_DB" -eq 1 ]]; then
        echo "  Preflight as ${ADMIN_USER}: CREATEDB, source encoding/locale, target owner, active connections"
        echo "  Drop ${TARGET_DB} only if it exists and has no active connections"
        echo "  Recreate ${TARGET_DB} from template0 with source encoding/locale and preserved or explicit owner"
    fi
    if [[ "$INPUT_FORMAT" == "sql" && "$CLEAN_RESTORE" -eq 1 ]]; then
        echo "  Preflight as ${MAINTENANCE_USER}: target ownership, application role, schema ownership, active connections"
        echo "  Grant ${DB_USER} temporary CREATE on ${TARGET_DB} only if needed"
        echo "  Remove ${RESTORE_SCHEMA} as ${MAINTENANCE_USER} first only when that role owns it"
        echo "  Replace ${RESTORE_SCHEMA} transactionally as ${DB_USER}; the database itself is preserved"
        echo "  Revoke any temporary CREATE privilege after restore or failure"
    fi
    if [[ -n "$TEMP_LIST_FILE" ]]; then
        if [[ "$CLEAN_RESTORE" -eq 1 ]]; then
            printf '  %q' pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" --clean --if-exists --no-owner --no-privileges -v --use-list="<generated temp list>" "$INPUT"
        else
            printf '  %q' pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$TARGET_DB" --no-owner --no-privileges -v --use-list="<generated temp list>" "$INPUT"
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
    recreate_target_database
elif [[ "$INPUT_FORMAT" == "sql" && "$CLEAN_RESTORE" -eq 1 ]]; then
    prepare_plain_sql_clean_restore
fi

if [[ -n "$DB_PASS" ]]; then
    PGPASSWORD="$DB_PASS" "${RESTORE_CMD[@]}"
else
    env -u PGPASSWORD "${RESTORE_CMD[@]}"
fi

echo "Restore complete into ${TARGET_DB}"

if [[ "$VERIFY_AFTER" -eq 1 ]]; then
    echo "Running verification against ${TARGET_DB}"
    if [[ -n "$DB_PASS" ]]; then
        PGPASSWORD="$DB_PASS" DB_DATABASE="$TARGET_DB" DB_HOSTNAME_READ="$DB_HOST" DB_PORT="$DB_PORT" DJANGO_USER="$DB_USER" DB_SCHEMA="$DB_SCHEMA" DB_SSLMODE="$DB_SSLMODE" \
            "${ROOT_DIR}/database/verify_db.sh"
    else
        env -u PGPASSWORD DB_DATABASE="$TARGET_DB" DB_HOSTNAME_READ="$DB_HOST" DB_PORT="$DB_PORT" DJANGO_USER="$DB_USER" DB_SCHEMA="$DB_SCHEMA" DB_SSLMODE="$DB_SSLMODE" \
            "${ROOT_DIR}/database/verify_db.sh"
    fi
fi
