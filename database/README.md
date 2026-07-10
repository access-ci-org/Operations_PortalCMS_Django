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
Restore from a dump file. Refuses to restore into the live database unless `--allow-live-target` is set. Supports `--recreate-db` and `--dry-run`.

```bash
./database/pg_restore_portal.sh \
  --input database/dumps/portal1_<timestamp>.dump \
  --target-db portal1_clone \
  --recreate-db
```

## See Also

- [dev_documentation/CURRENT_STATE.md](../dev_documentation/CURRENT_STATE.md) - Current operational state, verification results, and APP_CONFIG reference
