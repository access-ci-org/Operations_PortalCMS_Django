# Database Scripts

This directory contains database management scripts for the Operations Portal CMS.

Current environment note:

- As of 2026-04-24, the database of record is Amazon RDS `portal1`.
- The deployed runtime config is `/soft/django-cms-01/conf/portal.conf.dev.json`.
- The application role/schema is `portal_django` / `portal_django`.
- The database owner is `portal_owner`.
- The RDS host is `opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com`.
- SSL mode is `require`.
- Local `portalcms1` and `portalcms1_clone` references are retained as historical/local-helper examples only.

Current verification note:

- `verify_db.sh` was run read-only against RDS `portal1` on 2026-04-24.
- It found 66 application tables, 45 sequences, 206 migration rows, and no ownership issues.
- `pg_dump_cms.sh --dry-run` resolves the RDS `portal1` target correctly through `APP_CONFIG`.
- Restore/recreate flows should still be treated carefully on RDS because database creation/drop privileges can differ from local PostgreSQL.
- `clone_db.sh` intentionally refuses non-local hosts unless `--allow-remote-host` is supplied.

## APP_CONFIG For Helper Scripts

Database helper scripts should be run with explicit `APP_CONFIG`.

Examples:

```bash
APP_CONFIG="$HOME/.config/operations-portal-cms/portal.local.json" ./database/verify_db.sh
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh --dry-run
```

Before any restore, migration, sync, or mutating test command, confirm the resolved database host/name are the intended local or maintenance target.

## Scripts

### verify_db.sh

Verifies database schema, ownership, and structure.

**Usage:**
```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
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
- `DB_DATABASE` - Database name from `APP_CONFIG` when set; shell override supported
- `DJANGO_USER` - Database user (default: portal_django)
- `DB_HOSTNAME_READ` - Database host (default: localhost)
- `DB_PORT` - Database port (default: 5432)
- `DB_SCHEMA` - Optional schema override for tooling; auto-detected from `django_migrations` when unset
- `DB_SEARCH_PATH` - Runtime PostgreSQL search path (recommended: `"$user",public`)
- `DB_SSLMODE` - Optional PostgreSQL SSL mode for remote databases such as Amazon RDS (recommended: `require`)

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
- config discovery from `APP_CONFIG` first, with repo-root `portal.conf.dev.json` as the canonical local fallback and older repo-root names treated as legacy fallbacks
- explicit source database override
- custom or SQL dump output
- dry-run preview mode for local or production planning

This script is suitable for:
- local clone/test workflows
- RDS backup workflows, as long as the environment variables or `APP_CONFIG` point at the intended RDS instance

**Usage:**
```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh --source-db portal1 --format sql
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh --dry-run
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
- local clone/restore workflows
- carefully planned RDS restores, provided the target host/database/user are set deliberately and `--allow-live-target` is only used when intended

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

### Local Mac From RDS Backup

Future developers should use a local PostgreSQL restore of a current RDS `portal1` backup for Mac/local work. They should not point a local Mac `APP_CONFIG` at the shared RDS host.

Migrations only synchronize schema. They do not copy CMS pages, news, users, permissions, CIDER rows, or uploaded media from RDS. A current `portal1` backup already includes the application data and, as of the latest verification pass, is already migrated for this codebase.

Safe local sequence after restoring the backup:

```bash
APP_CONFIG=/path/to/local-mac-config.json uv run python manage.py check
APP_CONFIG=/path/to/local-mac-config.json uv run python manage.py migrate --plan
APP_CONFIG=/path/to/local-mac-config.json uv run python manage.py migrate
```

Expected result for a current backup is no planned migration operations. If the backup is older, Django may apply migrations forward, but only to that local restored database.

Make sure the local `APP_CONFIG` points at local PostgreSQL and uses a search path/schema that matches the restore. For the current RDS layout, the app objects live in schema `portal_django`; either restore/use a matching `portal_django` role and schema with `DB_SEARCH_PATH="\"$user\",public"`, or set an equivalent local search path such as `portal_django,public`.

CIDER sync is separate from migrations. Running `sync_cider_from_api` on a Mac will read CIDER and update only the local restored database. Skip it if the goal is to keep the local database exactly as restored from the backup.

### Verify Database
```bash
# Check if everything looks correct
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
```

### Create Full Backup
```bash
# Interactive backup
./database/backup_db.sh
# Choose option 2 for SQL format

# Current helper-driven backup preview
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh --dry-run

# Current helper-driven custom-format backup
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh

# Current helper-driven SQL backup
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh --format sql
```

### Transfer to Remote Server
```bash
# Copy dump file
scp database/dumps/portal1_*.dump software@your-server:/tmp/

# OR for SQL format
gzip database/dumps/portal1_*.sql
scp database/dumps/portal1_*.sql.gz software@your-server:/tmp/
```

### Restore on Remote Server
```bash
# SSH to server
ssh software@your-server

# For custom format dump
./database/pg_restore_cms.sh \
  --input /tmp/portal1_*.dump \
  --target-db portal1 \
  --allow-live-target

# For SQL format dump
gunzip /tmp/portal1_*.sql.gz
./database/pg_restore_cms.sh \
  --input /tmp/portal1_*.sql \
  --target-db portal1 \
  --allow-live-target
```

### Safe Clone Workflow
```bash
# Preview the exact local clone steps first
./database/clone_db.sh portalcms1_clone backups/portalcms1_pre_versioning_20260331T174604Z.dump --dry-run

# Create a disposable local clone from the current safety backup
./database/clone_db.sh

# Or be explicit
./database/pg_restore_cms.sh \
  --input backups/portalcms1_pre_versioning_20260331T174604Z.dump \
  --target-db portalcms1_clone \
  --recreate-db
```

## Database Migration Workflow

### Current RDS Backup/Restore Workflow

1. **Verify current database:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
   ```

2. **Create backup:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_cms.sh
   ```

3. **Transfer to server:**
   ```bash
   scp database/dumps/portal1_*.dump software@your-server:/tmp/
   ```

4. **Restore on server:**
   ```bash
   ssh software@your-server
   cd /soft/django-cms-01/PROD

   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
     ./database/pg_restore_cms.sh \
       --input /tmp/portal1_*.dump \
       --target-db portal1 \
       --allow-live-target
   ```

5. **Verify restoration:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
   ```

6. **Restart application:**
   ```bash
   sudo systemctl restart portal
   ```

## Troubleshooting

### Permission Denied
```bash
# Check environment variables
echo $DB_DATABASE $DJANGO_USER

# Or set them explicitly
export APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json
export DB_DATABASE=portal1
export DJANGO_USER=portal_django
export DB_SCHEMA=portal_django
./database/verify_db.sh
```

### Tables Owned by Wrong User
```bash
# Fix ownership in a local PostgreSQL clone environment (run as postgres user)
sudo -u postgres psql -d portalcms1_clone -c \
  "REASSIGN OWNED BY old_owner TO portal_django;"
```

### Database Connection Failed
```bash
# Check if local PostgreSQL is running
sudo systemctl status postgresql

# Check the current RDS connection through the helper
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
```

### Role + Schema Cutover
Use the dedicated cutover script in:

- `database/portal_django_cutover.psql`

That script handles:

- renaming the PostgreSQL role from `portalcms_django` to `portal_django`
- creating the `portal_django` schema
- moving app-owned objects from `public` into `portal_django`
- setting the role search path to `"$user", public`
- hardening `public` by revoking broad create access

## See Also

- [CURRENT_STATE.md](../READMEs/CURRENT_STATE.md) - Latest verified runtime, database, content, and check results
- [database_migration_plan.md](../READMEs/database_migration_plan.md) - RDS cutover status and rollback notes
- [APP_CONFIG_CONTRACT.md](../READMEs/APP_CONFIG_CONTRACT.md) - Runtime config contract
