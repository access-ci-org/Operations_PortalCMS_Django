# CIDER Data Integration

## Overview

This Django CMS keeps a local copy of CIDER catalog data in PostgreSQL and uses that data in forms, permissions, and news workflows.

The app should query local tables at request time; CIDER API calls should happen in background sync jobs.

Last checked against RDS `portal1`: 2026-04-24. See [CURRENT_STATE.md](./CURRENT_STATE.md) for the full runtime/database snapshot.

## API Sources

Primary endpoints:

1. `GET https://operations-api.access-ci.org/wh2/cider/v2/access-active/`
- Authoritative list of active infrastructure resources
- Used to sync `CiderInfrastructure`

2. `GET https://operations-api.access-ci.org/wh2/cider/v2/access-active-groups/`
- Active groups + rollups + organizations + feature catalogs
- Used to sync `CiderGroups`, `CiderOrganizations`, and `CiderFeatures`

## Local Models Synced

- `CiderInfrastructure` from `v2/access-active/`
- `CiderGroups` from `v2/access-active-groups/` `active_groups`
- `CiderOrganizations` from `v2/access-active-groups/` `organizations`
- `CiderFeatures` from `v2/access-active-groups/` `feature_categories` + `features`

## Command

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api
```

Useful options:

```bash
# Validate only (no DB writes)
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api --dry-run

# Filter groups by prefix when needed
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api --group-prefix rp.

# Skip one side of the sync (debug/partial operation)
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api --skip-infrastructure
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api --skip-groups-bundle

# Prune local CIDER groups that disappeared from active_groups
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api --dry-run --skip-infrastructure --prune-stale-groups
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api --skip-infrastructure --prune-stale-groups
```

## Current RDS Snapshot

The current RDS tables contain:

- `CiderInfrastructure`: 81 rows
- `CiderGroups`: 26 rows
- `CiderOrganizations`: 24 rows
- `CiderFeatures`: 14 rows

The latest dry-run against the live Operations API fetched:

- infrastructure: 78
- groups: 26
- organizations: 21
- feature categories: 14
- features: 54

Latest write result:

- 78 infrastructure rows updated
- 26 group rows updated
- 21 organization rows updated
- 14 feature category rows updated
- 2 stale local CIDER group rows pruned

Important: the sync command updates or creates rows by default. Local CIDER groups that disappeared from the API response are only deleted when `--prune-stale-groups` is explicitly used. Stale infrastructure, organization, and feature pruning is not currently implemented.

## News Form Impact

- `SystemStatusNews` affected infrastructure options come from local `CiderInfrastructure`.
- `IntegrationNews` affected elements remain local static choices in app models.
- Better CIDER sync quality reduces unmatched warnings during Drupal import and improves add/edit picker accuracy.

## Scheduling Guidance

Recommended cadence:

- Minimum: nightly sync
- Better freshness: every 6-12 hours
- Also run on-demand before major imports/reconciliations

Example crontab:

```cron
# Nightly full sync at 02:15 UTC
15 2 * * * cd /soft/django-cms-01/PROD && APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json /home/jlambertson/.local/bin/uv run python manage.py sync_cider_from_api >> /soft/django-cms-01/var/cider_sync.log 2>&1

# Optional midday refresh at 14:15 UTC
15 14 * * * cd /soft/django-cms-01/PROD && APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json /home/jlambertson/.local/bin/uv run python manage.py sync_cider_from_api >> /soft/django-cms-01/var/cider_sync.log 2>&1
```

Ansible direction:

- Use the `ansible.builtin.cron` module (or a systemd timer) to install the schedule.
- Keep logs in a known path and monitor failures.
- Validate in CI with `--dry-run` before deploy.

## Permissions Note

CIDER sync is metadata sync only. It does not grant user permissions directly. Permission mapping still relies on your authentication/group workflow.

The current auth group table still contains the older five RP-style group pairs plus the three operations URN groups. Decide deliberately before running `setup_rp_permissions` against all current `CiderGroups`, because that command writes Django groups and permissions. Use `setup_rp_permissions --dry-run` first.
