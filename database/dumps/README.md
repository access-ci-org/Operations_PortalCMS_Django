# Database and Media Dumps

This directory contains historical deployment dump notes and is still the default output directory for the helper dump script.

## Current Policy

- The database of record is Amazon RDS `portal1`.
- Use `APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_portal.sh` from the repo root for current backups.
- Current backups should not be committed to git.
- Restore operations into `portal1` require an explicit `--allow-live-target` and should be treated as a maintenance-window action.

## Historical Initial Deployment Files

- `portalcms_production_20260216_133655.sql.gz` - Initial database dump from local `djangocmsjoy`
  - Contains: initial tables, CMS pages, users, and news items
  - Historical target database: `portalcms1`
  - Historical user transition: `jelambeadmin` to `portalcms_django`

- `media_backup_20260216_134007.tar.gz` - Initial media files archive
  - Contains: uploaded images
  - Includes: `filer_public/` and `filer_public_thumbnails/` directories

These files are not the current production data source. Keep them only as historical bootstrap artifacts.

## Current Backup Usage

From the repo root:

```bash
# List available S3 dumps (most recent first by upload time)
uv run database/portal_db_retrieve.py -l

# Download and decompress the most recent portal1 dump from S3
uv run database/portal_db_retrieve.py -r

# Or dump directly from RDS (requires APP_CONFIG)
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/pg_dump_portal.sh
```

## Media

The repo also contains current media trees under `media/` and `database/media/`. Media backup/restore should be handled separately from PostgreSQL dumps.

If restoring a historical media archive, verify the target path first. The active nginx config serves media from:

```text
/soft/django-cms-01/PROD/media/
```

## Related Docs

- [database/README.md](../README.md)
- [Current Project State](../../READMEs/CURRENT_STATE.md)
- [Database Migration Status](../../READMEs/database_migration_plan.md)
