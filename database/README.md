# Database and Media Recovery Scripts

These scripts support hands-on backup, retrieval, restore, and verification for the
ACCESS Operations Portal CMS. They are not infrastructure automation and do not run
from Ansible.

- Database of record: `portal1`
- Non-production restore targets: `portal_dev` and `portal_beta`
- Application role and schema: `portal_django`
- Database owner: `portal_owner`
- RDS host currently used by these environments:
  `opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com`

Never print or commit an application config, password file, database dump, or other
credential-bearing material.

## Configuration used by each script

| Script | Configuration |
| --- | --- |
| `verify_db.sh`, `backup_db.sh`, `pg_dump_portal.sh` | Database environment variables or the JSON file named by `APP_CONFIG` |
| `pg_restore_portal.sh` | The same database configuration; on a deployed release it also auto-discovers `../../conf/portal.conf` |
| `portal_db_retrieve.py`, `media_retrieve.py` | AWS profile and S3 arguments only; they do not read `APP_CONFIG` |
| `media_restore.sh` | Archive path and target directory only |

On a deployed release such as `/soft/django-cms-01/tags/v0.6.4`, restore
auto-discovery resolves to:

```text
/soft/django-cms-01/conf/portal.conf
```

Outside that layout, pass a deliberately non-production config explicitly:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf \
  ./database/verify_db.sh
```

`APP_CONFIG` supplies the host, application role, application password, schema, SSL
settings, and configured database owner. The database represented by a downloaded dump
is separate and must be supplied with `--source-db`.

## Primary test: restore the latest portal1 S3 dump into portal_dev

Retrieval and restoration are separate operations:

- `portal_db_retrieve.py` selects and downloads a backup. Its `--target-db` option only
  places the target in the printed next-step command.
- `pg_restore_portal.sh` performs the destructive restore. It always requires an
  explicit `--target-db`.

### 1. Retrieve the latest portal1 dump

On the deployed server:

```bash
uv run database/portal_db_retrieve.py \
  -r \
  --profile newbackup \
  --target-db portal_dev
```

`portal1` is the default retrieval pattern. To select a particular epoch:

```bash
uv run database/portal_db_retrieve.py \
  -r "django.portal1.dump.<epoch>" \
  --profile newbackup \
  --target-db portal_dev
```

The compressed S3 artifact is classified from its decompressed content. Plain SQL is
saved with a `.sql` suffix; PostgreSQL custom archives are saved with `.dump`.
Retrieval prints a content-appropriate restore command but does not run it.

The current warehouse-management S3 producer runs plain `pg_dump` with
`-n portal_django` and without `--create`. Its artifact is therefore scoped to the
application schema and does not contain database creation or reconnect commands.

Local operators normally omit `--profile newbackup`; the default local profile is
`opsbackupreader`.

### 2. Supply portal_owner authentication

Plain-SQL clean restore preserves the existing target database but may need
`portal_owner` to remove an owner-controlled schema and temporarily grant
`portal_django` permission to recreate it. `portal_owner` does not need `CREATEDB`.

Use an operator-managed libpq password file:

```bash
export PGPASSFILE=/path/to/operator-managed.pgpass
```

Do not put the password directly in the restore command. The dump itself is restored
as `portal_django`, using the application credentials from the portal config.

### 3. Inspect the restore plan

Use the exact decompressed path printed by retrieval:

```bash
./database/pg_restore_portal.sh \
  --input database/dumps/django.portal1.dump.<epoch>.sql \
  --source-db portal1 \
  --target-db portal_dev \
  --clean-restore \
  --dry-run
```

Confirm that the output says:

```text
source db: portal1
target db: portal_dev
format:    sql
recreate:  0
clean restore: 1
```

### 4. Restore portal_dev

After reviewing the dry run:

```bash
./database/pg_restore_portal.sh \
  --input database/dumps/django.portal1.dump.<epoch>.sql \
  --source-db portal1 \
  --target-db portal_dev \
  --clean-restore
```

For plain SQL, the script:

1. Rejects database-level `CREATE`, `DROP`, or `ALTER DATABASE` statements and psql
   reconnect commands.
2. Refuses to clean the explicit source database.
3. Requires an existing target owned by the configured database owner.
4. Refuses a target with active client connections.
5. Requires a schema-complete dump that creates `portal_django`.
6. Preserves the target database, including its owner, encoding, locale, and
   database-level grants.
7. Replaces the application schema and restores the SQL through `psql` as
   `portal_django` in a single transaction.
8. Revokes any temporary database `CREATE` privilege after success or failure.
9. Runs `verify_db.sh` against the target unless `--no-verify` is supplied.

If `portal_owner` owns the existing application schema, its removal commits before the
application-role restore starts. A later restore failure can therefore leave this
disposable non-production target without the schema. Correct the failure and rerun the
same complete dump.

Plain SQL is restored with `psql`. PostgreSQL custom archives are restored with
`pg_restore`; the script selects the tool from the file contents rather than its name.

## Creating a compatible plain-SQL dump locally

`pg_dump_portal.sh --format sql` now produces a schema-complete, existing-database
restore:

- `--clean --if-exists`
- `--schema portal_django`
- `--no-owner --no-privileges`
- no `--create`

Therefore it includes the application schema and data but does not include
`CREATE/DROP DATABASE` or `\connect`.

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf \
  ./database/pg_dump_portal.sh \
    --source-db portal1 \
    --format sql
```

Use `--output PATH` to choose an explicit destination and `--dry-run` to inspect the
resolved `pg_dump` command without connecting:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf \
  ./database/pg_dump_portal.sh \
    --source-db portal1 \
    --format sql \
    --output database/dumps/portal1_test.sql \
    --dry-run
```

The interactive `backup_db.sh` uses the same compatible flags for option 2, “Full dump
(schema + data) - SQL format, existing-database restore.”

## Custom-format local sync

Custom format remains the default for `pg_dump_portal.sh` and is unchanged:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf \
  ./database/pg_dump_portal.sh \
    --source-db portal1
```

Restore that archive into an existing target:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf \
  ./database/pg_restore_portal.sh \
    --input database/dumps/portal1_full_<timestamp>.dump \
    --source-db portal1 \
    --target-db portal_dev \
    --clean-restore
```

Custom-format `--clean-restore` preserves the existing `portal_django` schema and
filters its `CREATE SCHEMA` entry from the archive. The target schema must already exist
and grant access to `portal_django`. One-time setup by `portal_owner`:

```bash
PGPASSFILE=/path/to/operator-managed.pgpass psql -w \
  -h opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com \
  -p 5432 -U portal_owner portal_dev \
  -c "CREATE SCHEMA IF NOT EXISTS portal_django; GRANT ALL ON SCHEMA portal_django TO portal_django;"
```

## Other database commands

List S3 database backups:

```bash
# portal1 default
uv run database/portal_db_retrieve.py -l

# another database
uv run database/portal_db_retrieve.py -l django.portal_dev.dump
```

Preview S3 database retrieval without downloading:

```bash
uv run database/portal_db_retrieve.py \
  -r \
  --profile newbackup \
  --target-db portal_dev \
  --dry-run
```

Run database verification explicitly:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf \
  DB_DATABASE=portal_dev \
  ./database/verify_db.sh
```

The optional `--recreate-db` restore mode drops and recreates the target database. It is
not used for the normal `portal1` to `portal_dev` refresh and requires a real
administrative role with `CREATEDB`, such as the documented `opsdba` role. Never pass
the literal placeholder `ADMIN_USER`.

## Matched database and media recovery point

Use the shared epoch when the database dump and media archive names correspond:

```bash
BACKUP_EPOCH=<epoch-from-s3-object-names>

uv run database/portal_db_retrieve.py \
  -r "django.portal1.dump.${BACKUP_EPOCH}" \
  --profile newbackup \
  --target-db portal_dev

uv run database/media_retrieve.py \
  -r "media.portal1.${BACKUP_EPOCH}." \
  --profile newbackup
```

Matching epochs select a candidate recovery pair. They do not prove that both uploads
completed successfully, came from the same scheduled run, or are transactionally
consistent.

## Media retrieval and restore

List or retrieve portal1 media backups:

```bash
uv run database/media_retrieve.py -l --profile newbackup
uv run database/media_retrieve.py -r --profile newbackup
```

Retrieved media archives default to `database/mediarestore/`. Preview extraction before
changing the media directory:

```bash
bash database/media_restore.sh \
  database/mediarestore/media.portal1.<epoch>.tar \
  --target-dir /soft/django-cms-01/www/media \
  --dry-run
```

Run the same command without `--dry-run` to extract. Media restoration merges into the
target directory and overwrites matching paths; it does not remove unrelated existing
files.

## Safety checklist

- Keep `--source-db portal1` and `--target-db portal_dev` explicit.
- Stop any application connected to `portal_dev` before clean restore.
- Inspect `--dry-run` before the real restore.
- Use `PGPASSFILE` for `portal_owner`; do not expose passwords in commands or logs.
- Do not commit files under `database/dumps/` or `database/mediarestore/`.
- Treat `portal1` as the protected source. The restore script refuses to target it
  unless the separate high-risk `--allow-live-target` override is deliberately used.
- Production backup scheduling, retention, monitoring, and restore testing remain the
  responsibility of `Operations_CMS_Infrastructure`.

## See also

- [Current application state](../dev_documentation/CURRENT_STATE.md)
- [Database role and schema setup](SETUP)
