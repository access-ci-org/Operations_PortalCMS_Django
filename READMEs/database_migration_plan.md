# Database Migration Status

This note records the Amazon RDS cutover that was completed on 2026-04-07 and the rollback assets that were kept afterward.

## Current Operational State

- Live service: `portal.service`
- Live runtime config: `/soft/django-cms-01/conf/portal.conf.dev.json`
- Live socket: `/soft/django-cms-01/run/portal.socket`
- Live database host: `opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com`
- Live database name: `portal1`
- Live database owner: `portal_owner`
- Live application role: `portal_django`
- Live application schema: `portal_django`
- Live search path: `"$user",public`
- Live SSL mode: `require`
- Last verified against RDS `portal1`: 2026-04-24
- Latest read-only verification: 66 application tables, 45 sequences, 206 migration rows, 0 unapplied migrations, and all application tables owned by `portal_django`

See [CURRENT_STATE.md](./CURRENT_STATE.md) for current row counts, CMS page titles, CIDER dry-run results, and verification command output.

## Completed On 2026-04-07

1. Verified the RDS target database and schema were reachable and empty.
2. Restored the current `portalcms1` dump into RDS `portal1`.
3. Validated Django connectivity, migration state, row counts, and app startup against a temporary RDS `APP_CONFIG`.
4. Took a final local pre-cutover dump from the original local PostgreSQL source.
5. Backed up the deployed runtime config.
6. Updated the live runtime config to point `portal.service` at RDS `portal1`.
7. Restarted `portal.service` and verified the live app through Gunicorn, Django, and the Unix socket.

## Rollback Assets

- Deployed config backup:
  `/soft/django-cms-01/conf/portal.conf.dev.pre_rds_cutover_20260407T192826Z.json`
- Final local pre-cutover dump:
  `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/portalcms1_pre_rds_cutover_20260407T192613Z.dump`
- Earlier RDS seed dump used during validation:
  `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/portalcms1_post_portal_cutover_20260407T132914Z.dump`

## Local Source Database

The original local PostgreSQL database was intentionally left in place for rollback and comparison work.

- Local source database name: `portalcms1`
- Local role/schema model retained there: `portal_django` / `portal_django`

Do not treat the local database as the active runtime target anymore. The active runtime target is RDS `portal1`.

## Current Cutover Logic

The runtime switch is still a config-target change, not a service rename.

The active deployed config now sets:

- `DB_HOSTNAME_READ`
- `DB_HOSTNAME_WRITE`
- `DB_DATABASE`
- `DB_SSLMODE`

Things that did not need to change for cutover:

- `portal.service`
- `portal.conf.dev.json` as the deployed filename
- Django app/module names
- the application role/schema names

## If Rollback Is Needed

1. Restore the backed-up deployed config file over `/soft/django-cms-01/conf/portal.conf.dev.json`.
2. Restart `portal.service`.
3. Verify the service is again pointing at the intended database target.
4. Keep the RDS database intact for investigation unless a separate recovery decision is made.

## Summary

The RDS migration is no longer a future plan item. The live app is now running against Amazon RDS `portal1`, with the pre-cutover local database and config backup preserved for fallback.
