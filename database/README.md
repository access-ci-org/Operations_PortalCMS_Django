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
# Clone workflow: drop and recreate target database.
# ADMIN_USER must have CREATEDB; provide credentials through libpq (prefer PGPASSFILE).
./database/pg_restore_portal.sh \
  --input database/dumps/portal1_<timestamp>.dump \
  --target-db portal1_clone \
  --recreate-db \
  --admin-user ADMIN_USER

# Sync workflow: drop and repopulate objects within an existing database
# (schema must already exist — see "One-time prerequisite" below)
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
./database/pg_restore_portal.sh \
  --input database/dumps/portal1_<timestamp>.dump \
  --target-db portal_dev \
  --clean-restore
```

## Getting RDS backups from S3

Use `database/portal_db_retrieve.py`. Requires the `opsbackupreader` AWS profile locally (or `--profile newbackup` on the production server). No `APP_CONFIG` needed for retrieval.

```bash
# List available portal1 dumps (production default)
uv run database/portal_db_retrieve.py -l

# List dumps for a specific database
uv run database/portal_db_retrieve.py -l django.portal_dev.dump

# Download and decompress the most recent portal1 dump
uv run database/portal_db_retrieve.py -r

# Download and decompress the most recent portal_dev dump
uv run database/portal_db_retrieve.py -r django.portal_dev.dump

# Dry run — show what would be downloaded without fetching
uv run database/portal_db_retrieve.py -r --dry-run
```

Downloads land in `database/dumps/` and are decompressed automatically. PostgreSQL
custom archives receive a `.dump` suffix and plain SQL receives `.sql`, based on the
decompressed content. The script selects the most recently uploaded file by S3
`LastModified` date.

For a conflict-free plain-SQL refresh, recreate an explicit non-source target. On a
deployed release, `pg_restore_portal.sh` auto-discovers `../../conf/portal.conf`.
The administrative role is used only for target preflight and recreation; the restore
still runs as the configured application role.

```bash
PGPASSFILE=/path/to/operator-managed.pgpass \
./database/pg_restore_portal.sh \
  --input database/dumps/django.portal1.dump.<epoch>.sql \
  --target-db portal_dev \
  --recreate-db \
  --admin-user ADMIN_USER
```

The script refuses to recreate the configured source database, refuses targets with
active connections, preserves an existing target owner, and recreates the target from
`template0` with the source database encoding and locale. If the target does not yet
exist, also pass `--owner OWNER`.

## Retrieving a matched database and media recovery point

When a database dump and media archive have a shared epoch in their S3 object names, use
that epoch when retrieving a recovery pair instead of running both retrieval scripts with
their independent "most recent" selection:

```bash
BACKUP_EPOCH=1784507401  # Replace with the epoch from the S3 object names.

uv run database/portal_db_retrieve.py \
  -r "django.portal1.dump.${BACKUP_EPOCH}"

uv run database/media_retrieve.py \
  -r "media.portal1.${BACKUP_EPOCH}."
```

Matching epochs let the tools select a candidate recovery pair. They do not by themselves
prove that both uploads completed successfully, that either artifact is intact, that the
artifacts came from the same scheduled run, or that the database and filesystem are
transactionally consistent. Production backup validation, retention, scheduling,
monitoring, and restore testing belong in `Operations_CMS_Infrastructure`.

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
