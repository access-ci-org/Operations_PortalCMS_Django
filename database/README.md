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

Safe dump script for the current Portal CMS PostgreSQL database.

Supports:
- config discovery from `APP_CONFIG`, `portalcms.conf.dev.json`, or `portalcms.conf.json`
- explicit source database override
- custom or SQL dump output
- dry-run preview mode for local or production planning

This script is suitable for:
- local clone/test workflows
- future RDS backup workflows, as long as the environment variables or `APP_CONFIG` point at the intended RDS instance

**Usage:**
```bash
./database/pg_dump_cms.sh
./database/pg_dump_cms.sh --source-db portalcms1 --format sql
./database/pg_dump_cms.sh --output database/dumps/portalcms1_clone_seed.dump
./database/pg_dump_cms.sh --dry-run
```

### pg_restore_cms.sh

Safe restore script for the current Portal CMS PostgreSQL database.

Supports:
- explicit input dump
- explicit target database
- optional drop/recreate of the target database
- refusal to restore into the configured live/source database unless explicitly overridden
- post-restore verification using `verify_db.sh`
- dry-run preview mode for local or production planning

This script is suitable for:
- local clone/restore workflows right now
- future RDS restores, provided the target host/database/user are set deliberately and `--allow-live-target` is only used when intended

**Usage:**
```bash
./database/pg_restore_cms.sh \
  --input backups/portalcms1_pre_versioning_20260331T174604Z.dump \
  --target-db portalcms1_clone \
  --recreate-db

./database/pg_restore_cms.sh \
  --input backups/portalcms1_pre_versioning_20260331T174604Z.dump \
  --target-db portalcms1_clone \
  --recreate-db \
  --dry-run
```

### clone_db.sh

Convenience wrapper for the clone-first workflow used for safe testing.

**Usage:**
```bash
./database/clone_db.sh
./database/clone_db.sh portalcms1_clone backups/portalcms1_pre_versioning_20260331T174604Z.dump
./database/clone_db.sh portalcms1_clone backups/portalcms1_pre_versioning_20260331T174604Z.dump --dry-run
```

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
./database/pg_restore_cms.sh \
  --input /tmp/portalcms1_*.dump \
  --target-db portalcms1 \
  --allow-live-target

# For SQL format dump
gunzip /tmp/portalcms1_*.sql.gz
./database/pg_restore_cms.sh \
  --input /tmp/portalcms1_*.sql \
  --target-db portalcms1 \
  --allow-live-target
```

### Safe Clone Workflow
```bash
# Preview the exact clone steps first
./database/clone_db.sh portalcms1_clone backups/portalcms1_pre_versioning_20260331T174604Z.dump --dry-run

# Create a disposable clone from the current safety backup
./database/clone_db.sh

# Or be explicit
./database/pg_restore_cms.sh \
  --input backups/portalcms1_pre_versioning_20260331T174604Z.dump \
  --target-db portalcms1_clone \
  --recreate-db
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
