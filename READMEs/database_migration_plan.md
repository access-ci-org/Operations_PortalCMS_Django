# Database Migration Plan

This note captures the current database migration strategy after the local role/schema/service/config cleanup completed on 2026-04-07.

## Current Local State

- Live service: `portal.service`
- Live runtime config: `/soft/django-cms-01/conf/portal.conf.dev.json`
- Live socket: `/soft/django-cms-01/run/portal.socket`
- Live local database name: `portalcms1`
- Live database role: `portal_django`
- Live application schema: `portal_django`
- Live search path: `"$user",public`

Important decision:

- Do **not** rename the local database from `portalcms1` to `portal1` yet.
- The next likely major step is seeding Amazon RDS from the current local database.
- Leaving the local database names alone avoids confusion during source-to-target migration and rollback planning.

## Migration Model

When moving to Amazon RDS, treat the work as two separate phases:

1. **Data seeding into RDS**
2. **Application cutover to RDS**

Do not combine them into a single rename-and-migrate event.

## Phase 1: Seed RDS

Goal:

- Keep the current application running against local PostgreSQL
- Build and validate the target RDS database separately

Recommended approach:

1. Keep the current local app pointed at local `portalcms1`
2. Create the target RDS database with the intended final name, likely `portal1`
3. Restore/import data from the local `portalcms1` source into the RDS `portal1` target
4. Apply any RDS-specific setup needed there

Expected RDS-side checks:

- database role exists as `portal_django`
- schema exists as `portal_django`
- role/search path resolves to `"$user",public`
- table ownership is correct
- row counts on key tables look right
- Django can connect read-only without error

At the end of Phase 1:

- the production app should still be using the local DB
- the RDS database should be validated but not yet live

## Phase 2: Cut App Over To RDS

Goal:

- Switch the existing app runtime from local PostgreSQL to the validated RDS database

This is primarily a connection-target change, not a service rename.

Things that should change at cutover time:

- `DB_HOSTNAME_READ`
- `DB_HOSTNAME_WRITE`
- `DB_DATABASE`
- possibly `DB_PORT`
- possibly additional SSL/connection options if required by RDS

Things that should **not** need to change at cutover time:

- `portal.service`
- `portal.conf.dev.json` as a filename
- Django app/module names
- database role/schema names, assuming RDS is prepared as `portal_django` / `portal_django`

## Recommended Future Cutover Sequence

1. Take a fresh local pre-RDS dump
2. Restore that dump into RDS `portal1`
3. Verify the RDS database independently
4. Create a temporary RDS app config for testing
5. Run Django read-only checks against the RDS config
6. Schedule the application cutover window
7. Take one final local backup immediately before the switch
8. Update the live app config to point to the RDS host and database
9. Restart `portal.service`
10. Verify Django, Gunicorn, and nginx behavior
11. Keep the local database untouched for rollback until confidence is high

## Recommended Testing Pattern

Before editing the live runtime config, use a temporary RDS config file for validation.

That lets us test:

- DB connectivity
- migrations state
- row counts
- schema resolution
- app startup

without prematurely flipping the production service.

## Why This Is The Preferred Path

- It avoids mixing local cleanup with RDS migration
- It keeps rollback simple
- It reduces confusion around source vs target database names
- It lets RDS use the final desired DB name (`portal1`) even while local stays on `portalcms1`

## Summary

For the local machine:

- keep using `portalcms1`
- keep `portal_django` role/schema
- keep `portal.service`

For the future RDS target:

- create and validate `portal1`
- cut the app over only after validation is complete
