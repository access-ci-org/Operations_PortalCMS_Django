#!/bin/bash
set -euo pipefail

# Database verification script for Operations Portal CMS
# Usage: ./database/verify_db.sh

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
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Operations Portal CMS - Database Verification${NC}"
echo "=============================================="
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

# Check if database exists and is reachable
if [[ "$(run_psql -t -A -c "SELECT current_database();" 2>/dev/null | xargs || true)" != "$DB_NAME" ]]; then
    echo -e "${RED}✗ Unable to connect to database '$DB_NAME' as $DB_USER${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Database exists: $DB_NAME${NC}"
echo ""

TARGET_SCHEMA="$(detect_schema)"
echo -e "${GREEN}✓ Application schema target: $TARGET_SCHEMA${NC}"
echo ""

# Check database owner
echo -e "${YELLOW}Database Information:${NC}"
echo "-----------------------------------"
run_psql -c "
SELECT 
    d.datname as database,
    pg_catalog.pg_get_userbyid(d.datdba) as owner,
    pg_size_pretty(pg_database_size(d.datname)) as size
FROM pg_catalog.pg_database d
WHERE d.datname = '$DB_NAME';
"

# List all schemas
echo ""
echo -e "${YELLOW}Schemas:${NC}"
echo "-----------------------------------"
run_psql -c "
SELECT 
    schema_name,
    schema_owner
FROM information_schema.schemata
WHERE schema_name NOT IN ('pg_catalog', 'information_schema')
ORDER BY schema_name;
"

# Count tables by schema
echo ""
echo -e "${YELLOW}Table Count by Schema:${NC}"
echo "-----------------------------------"
run_psql -c "
SELECT 
    schemaname as schema,
    COUNT(*) as table_count
FROM pg_tables
WHERE schemaname NOT IN ('pg_catalog', 'information_schema')
GROUP BY schemaname
ORDER BY schemaname;
"

# List all tables with ownership
echo ""
echo -e "${YELLOW}Tables and Ownership:${NC}"
echo "-----------------------------------"
run_psql -c "
SELECT 
    schemaname as schema,
    tablename as table,
    tableowner as owner
FROM pg_tables
WHERE schemaname = '$TARGET_SCHEMA'
ORDER BY tablename;
"

# Check for key Django tables
echo ""
echo -e "${YELLOW}Key Django CMS Tables:${NC}"
echo "-----------------------------------"
TABLES=(
    "auth_user"
    "cms_page"
    "django_migrations"
    "portal_systemstatusnews"
    "portal_systemstatusnewsitemplugin"
    "portal_systemstatusnews_affected_infrastructure_items"
    "portal_integrationnews"
    "portal_integrationnewsitemplugin"
    "portal_integrationnews_affected_elements"
    "portal_integrationelement"
)
for table in "${TABLES[@]}"; do
    REGCLASS=$(run_psql -t -A -c "SELECT to_regclass('\"${TARGET_SCHEMA}\".\"${table}\"');" | xargs)
    if [[ -n "$REGCLASS" ]]; then
        COUNT=$(run_psql -t -A -c "SELECT COUNT(*) FROM \"${TARGET_SCHEMA}\".\"${table}\";" | xargs)
        echo -e "${GREEN}✓ $table${NC} (rows: $COUNT)"
    else
        echo -e "${RED}✗ $table (not found)${NC}"
    fi
done

# Check sequences
echo ""
echo -e "${YELLOW}Sequences:${NC}"
echo "-----------------------------------"
SEQ_COUNT=$(run_psql -t -c "
SELECT COUNT(*)
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE c.relkind = 'S'
AND n.nspname = '$TARGET_SCHEMA';
" | xargs)
echo -e "Total sequences: ${GREEN}$SEQ_COUNT${NC}"

# Check for ownership issues
echo ""
echo -e "${YELLOW}Checking for Ownership Issues:${NC}"
echo "-----------------------------------"
WRONG_OWNER=$(run_psql -t -c "
SELECT COUNT(*) 
FROM pg_tables 
WHERE schemaname = '$TARGET_SCHEMA' 
AND tableowner != '$DB_USER';
" | xargs)

if [ "$WRONG_OWNER" -eq 0 ]; then
    echo -e "${GREEN}✓ All tables owned by $DB_USER${NC}"
else
    echo -e "${RED}⚠ Warning: $WRONG_OWNER tables not owned by $DB_USER${NC}"
    echo ""
    echo "Tables with incorrect ownership:"
    run_psql -c "
    SELECT tablename, tableowner 
    FROM pg_tables 
    WHERE schemaname = '$TARGET_SCHEMA' 
    AND tableowner != '$DB_USER';
    "
fi

# Database statistics
echo ""
echo -e "${YELLOW}Database Statistics:${NC}"
echo "-----------------------------------"
run_psql -c "
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) AS size
FROM pg_tables
WHERE schemaname = '$TARGET_SCHEMA'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"

echo ""
echo -e "${GREEN}Verification complete!${NC}"
