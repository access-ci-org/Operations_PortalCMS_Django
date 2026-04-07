#!/bin/bash
set -euo pipefail

# Database dump script for Operations Portal CMS
# Usage: ./database/backup_db.sh

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DUMP_DIR="${ROOT_DIR}/database/dumps"
DATE=$(date +%Y%m%d_%H%M%S)

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

export_pg_env() {
    if [[ -n "${DB_PASS}" ]]; then
        export PGPASSWORD="${DB_PASS}"
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
}

run_psql() {
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" "$@"
}

# Configuration
DB_NAME="${DB_DATABASE:-$(load_config_value DB_DATABASE)}"
DB_NAME="${DB_NAME:-portalcms1}"
DB_USER="${DJANGO_USER:-$(load_config_value DJANGO_USER)}"
DB_USER="${DB_USER:-portal_django}"
DB_PASS="${DJANGO_PASS:-$(load_config_value DJANGO_PASS)}"
DB_HOST="${DB_HOSTNAME_READ:-$(load_config_value DB_HOSTNAME_READ)}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-$(load_config_value DB_PORT)}"
DB_PORT="${DB_PORT:-5432}"
DB_SCHEMA="${DB_SCHEMA:-$(load_config_value DB_SCHEMA)}"
DB_SSLMODE="${DB_SSLMODE:-$(load_config_value DB_SSLMODE)}"
DB_SSLROOTCERT="${DB_SSLROOTCERT:-$(load_config_value DB_SSLROOTCERT)}"
DB_SSLCERT="${DB_SSLCERT:-$(load_config_value DB_SSLCERT)}"
DB_SSLKEY="${DB_SSLKEY:-$(load_config_value DB_SSLKEY)}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Operations Portal CMS - Database Backup${NC}"
echo "========================================"
echo ""

export_pg_env

detect_schema() {
    if [[ -n "$DB_SCHEMA" ]]; then
        printf '%s\n' "$DB_SCHEMA"
        return
    fi

    local detected_schema
    detected_schema=$(run_psql -t -A -c "
SELECT schemaname
FROM pg_tables
WHERE tablename = 'django_migrations'
ORDER BY
    CASE
        WHEN schemaname = current_user THEN 0
        WHEN schemaname = 'public' THEN 1
        ELSE 2
    END,
    schemaname
LIMIT 1;
" 2>/dev/null | xargs || true)

    if [[ -n "$detected_schema" ]]; then
        printf '%s\n' "$detected_schema"
    else
        printf 'public\n'
    fi
}

# Create dump directory
mkdir -p "$DUMP_DIR"

# Check if database exists and is reachable
if [[ "$(run_psql -t -A -c "SELECT current_database();" 2>/dev/null | xargs || true)" != "$DB_NAME" ]]; then
    echo -e "${RED}Error: Unable to connect to database '$DB_NAME' as $DB_USER${NC}"
    exit 1
fi

echo -e "${YELLOW}Database: $DB_NAME${NC}"
echo -e "${YELLOW}User: $DB_USER${NC}"
echo -e "${YELLOW}Host: $DB_HOST:$DB_PORT${NC}"
if [[ -n "$DB_SSLMODE" ]]; then
    echo -e "${YELLOW}SSL mode: $DB_SSLMODE${NC}"
fi
TARGET_SCHEMA="$(detect_schema)"
echo -e "${YELLOW}Schema: $TARGET_SCHEMA${NC}"
echo ""

# Verify schema ownership
echo -e "${YELLOW}Verifying schema ownership...${NC}"
OWNER=$(run_psql -t -c "
SELECT pg_catalog.pg_get_userbyid(d.datdba) as owner
FROM pg_catalog.pg_database d
WHERE d.datname = '$DB_NAME';
" | xargs)

echo -e "Database owner: ${GREEN}$OWNER${NC}"

# Count tables
TABLE_COUNT=$(run_psql -t -c "
SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = '$TARGET_SCHEMA';
" | xargs)

echo -e "Tables: ${GREEN}$TABLE_COUNT${NC}"
echo ""

# Prompt for dump type
echo "Select dump type:"
echo "  1) Full dump (schema + data) - Custom format"
echo "  2) Full dump (schema + data) - SQL format"
echo "  3) Data only dump"
echo "  4) Schema only dump"
read -p "Choice [1-4]: " CHOICE

case $CHOICE in
    1)
        FILENAME="${DUMP_DIR}/${DB_NAME}_full_${DATE}.dump"
        echo -e "${YELLOW}Creating custom format dump...${NC}"
        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -F c -b -v -f "$FILENAME"
        ;;
    2)
        FILENAME="${DUMP_DIR}/${DB_NAME}_full_${DATE}.sql"
        echo -e "${YELLOW}Creating SQL dump...${NC}"
        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            --clean --if-exists --create -v -f "$FILENAME"
        ;;
    3)
        FILENAME="${DUMP_DIR}/${DB_NAME}_data_${DATE}.sql"
        echo -e "${YELLOW}Creating data-only dump...${NC}"
        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -a --disable-triggers -v -f "$FILENAME"
        ;;
    4)
        FILENAME="${DUMP_DIR}/${DB_NAME}_schema_${DATE}.sql"
        echo -e "${YELLOW}Creating schema-only dump...${NC}"
        pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" \
            -s -v -f "$FILENAME"
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

# Check if dump was successful
if [ $? -eq 0 ]; then
    # Get file size
    SIZE=$(du -h "$FILENAME" | cut -f1)
    
    echo ""
    echo -e "${GREEN}✓ Dump completed successfully${NC}"
    echo -e "File: ${GREEN}$FILENAME${NC}"
    echo -e "Size: ${GREEN}$SIZE${NC}"
    
    # Offer to compress
    if [[ "$FILENAME" == *.sql ]]; then
        read -p "Compress with gzip? (y/N): " COMPRESS
        if [[ $COMPRESS =~ ^[Yy]$ ]]; then
            gzip "$FILENAME"
            SIZE=$(du -h "${FILENAME}.gz" | cut -f1)
            echo -e "${GREEN}✓ Compressed: ${FILENAME}.gz ($SIZE)${NC}"
            FILENAME="${FILENAME}.gz"
        fi
    fi

    echo ""
    if [[ "$DB_HOST" == "localhost" || "$DB_HOST" == "127.0.0.1" ]]; then
        echo "To transfer to remote server:"
        echo "  scp $FILENAME software@your-server:/tmp/"
        echo ""
    fi
else
    echo -e "${RED}✗ Dump failed${NC}"
    exit 1
fi
