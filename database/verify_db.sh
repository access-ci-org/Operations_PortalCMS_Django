#!/bin/bash
# Database verification script for Operations Portal CMS
# Usage: ./database/verify_db.sh

# Configuration
DB_NAME="${DB_DATABASE:-portalcms1}"
DB_USER="${DJANGO_USER:-portal_django}"
DB_HOST="${DB_HOSTNAME_READ:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_SCHEMA="${DB_SCHEMA:-}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Operations Portal CMS - Database Verification${NC}"
echo "=============================================="
echo ""

detect_schema() {
    if [[ -n "$DB_SCHEMA" ]]; then
        printf '%s\n' "$DB_SCHEMA"
        return
    fi

    local detected_schema
    detected_schema=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "
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

# Check if database exists
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${RED}✗ Database '$DB_NAME' not found${NC}"
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
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
TABLES=("auth_user" "cms_page" "django_migrations" "operations_portalcms_django_integrationnews" "operations_portalcms_django_systemstatusnews")
for table in "${TABLES[@]}"; do
    REGCLASS=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT to_regclass('\"${TARGET_SCHEMA}\".\"${table}\"');" | xargs)
    if [[ -n "$REGCLASS" ]]; then
        COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -A -c "SELECT COUNT(*) FROM \"${TARGET_SCHEMA}\".\"${table}\";" | xargs)
        echo -e "${GREEN}✓ $table${NC} (rows: $COUNT)"
    else
        echo -e "${RED}✗ $table (not found)${NC}"
    fi
done

# Check sequences
echo ""
echo -e "${YELLOW}Sequences:${NC}"
echo "-----------------------------------"
SEQ_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
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
WRONG_OWNER=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
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
    psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -c "
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
