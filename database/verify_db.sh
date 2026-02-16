#!/bin/bash
# Database verification script for Operations Portal CMS
# Usage: ./database/verify_db.sh

# Configuration
DB_NAME="${DB_DATABASE:-portalcms1}"
DB_USER="${DJANGO_USER:-portalcms_django}"
DB_HOST="${DB_HOSTNAME_READ:-localhost}"
DB_PORT="${DB_PORT:-5432}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

echo -e "${BLUE}Operations Portal CMS - Database Verification${NC}"
echo "=============================================="
echo ""

# Check if database exists
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${RED}✗ Database '$DB_NAME' not found${NC}"
    exit 1
fi

echo -e "${GREEN}✓ Database exists: $DB_NAME${NC}"
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
WHERE schemaname = 'public'
ORDER BY tablename;
"

# Check for key Django tables
echo ""
echo -e "${YELLOW}Key Django CMS Tables:${NC}"
echo "-----------------------------------"
TABLES=("auth_user" "cms_page" "django_migrations" "operations_portalcms_django_integrationnews" "operations_portalcms_django_systemstatusnews")
for table in "${TABLES[@]}"; do
    if psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "\dt $table" | grep -q "$table"; then
        COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "SELECT COUNT(*) FROM $table;" | xargs)
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
FROM information_schema.sequences 
WHERE sequence_schema = 'public';
" | xargs)
echo -e "Total sequences: ${GREEN}$SEQ_COUNT${NC}"

# Check for ownership issues
echo ""
echo -e "${YELLOW}Checking for Ownership Issues:${NC}"
echo "-----------------------------------"
WRONG_OWNER=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT COUNT(*) 
FROM pg_tables 
WHERE schemaname = 'public' 
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
    WHERE schemaname = 'public' 
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
WHERE schemaname = 'public'
ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC
LIMIT 10;
"

echo ""
echo -e "${GREEN}Verification complete!${NC}"
