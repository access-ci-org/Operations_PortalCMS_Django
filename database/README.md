# Database Scripts

This directory contains database management scripts for the Operations Portal CMS.

## Scripts

### verify_db.sh

Verifies database schema, ownership, and structure.

**Usage:**
```bash
./database/verify_db.sh
```

**Checks:**
- Database existence and owner
- Schema ownership
- Table counts and ownership
- Key Django CMS tables
- Sequence counts
- Ownership issues
- Database size and statistics

**Environment Variables:**
- `DB_DATABASE` - Database name (default: portalcms1)
- `DJANGO_USER` - Database user (default: portalcms_django)
- `DB_HOSTNAME_READ` - Database host (default: localhost)
- `DB_PORT` - Database port (default: 5432)

### backup_db.sh

Interactive database backup script with multiple dump format options.

**Usage:**
```bash
./database/backup_db.sh
```

**Dump Types:**
1. Full dump (schema + data) - Custom format (binary, use with pg_restore)
2. Full dump (schema + data) - SQL format (human-readable)
3. Data only dump (no schema)
4. Schema only dump (no data)

**Output:**
Dumps are saved to `database/dumps/` directory with timestamp.

**Environment Variables:**
- Same as verify_db.sh

### pg_dump_cms.sh

Legacy dump script (from previous CMS version).

### pg_restore_cms.sh

Legacy restore script (from previous CMS version).

## Quick Examples

### Verify Database
```bash
# Check if everything looks correct
./database/verify_db.sh
```

### Create Full Backup
```bash
# Interactive backup
./database/backup_db.sh
# Choose option 2 for SQL format

# Manual backup (custom format)
pg_dump -U portalcms_django -d portalcms1 -F c -b \
  -f database/dumps/backup_$(date +%Y%m%d).dump

# Manual backup (SQL format)
pg_dump -U portalcms_django -d portalcms1 --clean --if-exists \
  -f database/dumps/backup_$(date +%Y%m%d).sql
```

### Transfer to Remote Server
```bash
# Copy dump file
scp database/dumps/portalcms1_*.dump software@your-server:/tmp/

# OR for SQL format
gzip database/dumps/portalcms1_*.sql
scp database/dumps/portalcms1_*.sql.gz software@your-server:/tmp/
```

### Restore on Remote Server
```bash
# SSH to server
ssh software@your-server

# For custom format dump
pg_restore -U portalcms_django -d portalcms1 -v \
  --no-owner --no-acl /tmp/portalcms1_*.dump

# For SQL format dump
gunzip /tmp/portalcms1_*.sql.gz
psql -U portalcms_django -d portalcms1 -f /tmp/portalcms1_*.sql
```

## Database Migration Workflow

### From Development to Production

1. **Verify local database:**
   ```bash
   ./database/verify_db.sh
   ```

2. **Create backup:**
   ```bash
   ./database/backup_db.sh
   # Choose option 2 (SQL format)
   ```

3. **Transfer to server:**
   ```bash
   scp database/dumps/portalcms1_*.sql.gz software@your-server:/tmp/
   ```

4. **Restore on server:**
   ```bash
   ssh software@your-server
   cd /soft/django-cms-01/PROD/Operations_PortalCMS_Django
   
   # Decompress
   gunzip /tmp/portalcms1_*.sql.gz
   
   # Create database if needed
   sudo -u postgres psql -c "CREATE DATABASE portalcms1 OWNER portalcms_django;"
   
   # Restore
   psql -U portalcms_django -d portalcms1 -f /tmp/portalcms1_*.sql
   ```

5. **Verify restoration:**
   ```bash
   ./database/verify_db.sh
   ```

6. **Restart application:**
   ```bash
   sudo systemctl restart portalcms
   ```

## Troubleshooting

### Permission Denied
```bash
# Check environment variables
echo $DB_DATABASE $DJANGO_USER

# Or set them explicitly
export DB_DATABASE=portalcms1
export DJANGO_USER=portalcms_django
./database/verify_db.sh
```

### Tables Owned by Wrong User
```bash
# Fix ownership (run as postgres user)
sudo -u postgres psql -d portalcms1 -c \
  "REASSIGN OWNED BY old_owner TO portalcms_django;"
```

### Database Connection Failed
```bash
# Check if PostgreSQL is running
sudo systemctl status postgresql

# Check connection
psql -U portalcms_django -d portalcms1 -c "SELECT version();"
```

## See Also

- [DEPLOYMENT.md](../DEPLOYMENT.md) - Complete deployment guide with database migration section
- [QUICKREF.md](../QUICKREF.md) - Quick reference for common operations
