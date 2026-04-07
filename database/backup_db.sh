#!/bin/bash
# Database dump script for Operations Portal CMS
# Usage: ./database/backup_db.sh

# Configuration
DB_NAME="${DB_DATABASE:-portalcms1}"
DB_USER="${DJANGO_USER:-portal_django}"
DB_HOST="${DB_HOSTNAME_READ:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_SCHEMA="${DB_SCHEMA:-}"
DUMP_DIR="database/dumps"
DATE=$(date +%Y%m%d_%H%M%S)

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${YELLOW}Operations Portal CMS - Database Backup${NC}"
echo "========================================"
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

# Create dump directory
mkdir -p "$DUMP_DIR"

# Check if database exists
if ! psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -lqt | cut -d \| -f 1 | grep -qw "$DB_NAME"; then
    echo -e "${RED}Error: Database '$DB_NAME' not found${NC}"
    exit 1
fi

echo -e "${YELLOW}Database: $DB_NAME${NC}"
echo -e "${YELLOW}User: $DB_USER${NC}"
echo -e "${YELLOW}Host: $DB_HOST:$DB_PORT${NC}"
TARGET_SCHEMA="$(detect_schema)"
echo -e "${YELLOW}Schema: $TARGET_SCHEMA${NC}"
echo ""

# Verify schema ownership
echo -e "${YELLOW}Verifying schema ownership...${NC}"
OWNER=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
SELECT pg_catalog.pg_get_userbyid(d.datdba) as owner
FROM pg_catalog.pg_database d
WHERE d.datname = '$DB_NAME';
" | xargs)

echo -e "Database owner: ${GREEN}$OWNER${NC}"

# Count tables
TABLE_COUNT=$(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -t -c "
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
    echo "To transfer to remote server:"
    echo "  scp $FILENAME software@your-server:/tmp/"
    echo ""
else
    echo -e "${RED}✗ Dump failed${NC}"
    exit 1
fi
