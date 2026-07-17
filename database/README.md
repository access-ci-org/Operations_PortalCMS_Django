# Database Scripts

Ad-hoc developer scripts for backup, restore, and verification of the RDS database on `cms2.operations.access-ci.org`. These are **not** part of official infrastructure automation — they exist for hands-on CMS development work where a developer needs to inspect, dump, or restore data outside of normal deployment pipelines.

- Database of record: Amazon RDS `portal1`
- Runtime config: `/soft/django-cms-01/conf/portal.conf.dev.json`
- Application role/schema: `portal_django` / `portal_django`
- RDS host: `opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com`

All scripts read connection details from `APP_CONFIG`. Always pass it explicitly:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
```

## Scripts

### verify_db.sh
Read-only check of database schema, ownership, table counts, and sequences.

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
```

### backup_db.sh
Interactive backup — prompts for dump type (custom format, SQL, data-only, schema-only). Saves to `database/dumps/` with timestamp.

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/backup_db.sh
```

### pg_dump_portal.sh
Non-interactive dump script. Supports `--format sql`, `--source-db`, and `--dry-run`.

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_portal.sh
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_portal.sh --dry-run
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_portal.sh --format sql
```

### pg_restore_portal.sh
Restore from a dump file. Refuses to restore into the live database unless `--allow-live-target` is set. Supports `--recreate-db`, `--clean-restore`, and `--dry-run`.

```bash
# Clone workflow: drop and recreate target database (requires CREATEDB privilege)
./database/pg_restore_portal.sh \
  --input database/dumps/portal1_<timestamp>.dump \
  --target-db portal1_clone \
  --recreate-db

# Sync workflow: drop and repopulate objects within an existing database
# (schema must already exist — see "One-time prerequisite" below)
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
./database/pg_restore_portal.sh \
  --input database/dumps/portal1_<timestamp>.dump \
  --target-db portal_dev \
  --clean-restore
```

## See Also

- [dev_documentation/CURRENT_STATE.md](../dev_documentation/CURRENT_STATE.md) - Current operational state, verification results, and APP_CONFIG reference

## Syncing portal_dev from portal1

Use this workflow to overwrite `portal_dev` with a fresh copy of `portal1` data.

### One-time prerequisite: schema setup in portal_dev

The `portal_django` schema must exist in `portal_dev` and have been granted to the `portal_django` user. This is an admin-only step (requires `portal_owner` credentials, available from the infra repo):

```bash
PGPASSWORD='<portal_owner_password>' psql \
  -h opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com \
  -p 5432 -U portal_owner portal_dev \
  -c "CREATE SCHEMA IF NOT EXISTS portal_django; GRANT ALL ON SCHEMA portal_django TO portal_django;"
```

This only needs to be done once. Subsequent syncs leave the schema in place.

### Repeatable sync

```bash
# 1. Dump portal1
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
  ./database/pg_dump_portal.sh

# 2. Restore into portal_dev (drops and repopulates all objects, preserves schema)
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
  ./database/pg_restore_portal.sh \
    --input database/dumps/portal1_full_<timestamp>.dump \
    --target-db portal_dev \
    --clean-restore

# 3. Verify (run automatically by pg_restore_portal.sh, but can also run standalone)
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
  DB_DATABASE=portal_dev ./database/verify_db.sh
```

### Notes

- Stop any application processes pointing at `portal_dev` before running the restore — active connections will cause DROP statements to fail.
- If `PGPASSWORD` is set in your shell from a previous `portal_django` session, unset it before running admin psql commands as `portal_owner`: `unset PGPASSWORD`.
- `--clean-restore` uses `pg_restore --clean --if-exists` and automatically filters the schema creation out of the TOC. The `portal_django` schema is preserved; all tables and data are replaced.
