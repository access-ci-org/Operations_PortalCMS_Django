# CIDER Data Integration

## Overview

This Django CMS keeps a local copy of CIDER catalog data in PostgreSQL and uses that data in forms, permissions, and news workflows.

The app should query local tables at request time; CIDER API calls should happen in background sync jobs.

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
uv run python manage.py sync_cider_from_api
```

Useful options:

```bash
# Validate only (no DB writes)
uv run python manage.py sync_cider_from_api --dry-run

# Filter groups by prefix when needed
uv run python manage.py sync_cider_from_api --group-prefix rp.

# Skip one side of the sync (debug/partial operation)
uv run python manage.py sync_cider_from_api --skip-infrastructure
uv run python manage.py sync_cider_from_api --skip-groups-bundle
```

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
15 2 * * * cd /soft/django-cms-01/tags/Operations_PortalCMS_Django && /usr/bin/env bash -lc 'source .env && uv run python manage.py sync_cider_from_api >> /soft/django-cms-01/var/cider_sync.log 2>&1'

# Optional midday refresh at 14:15 UTC
15 14 * * * cd /soft/django-cms-01/tags/Operations_PortalCMS_Django && /usr/bin/env bash -lc 'source .env && uv run python manage.py sync_cider_from_api >> /soft/django-cms-01/var/cider_sync.log 2>&1'
```

Ansible direction:

- Use the `ansible.builtin.cron` module (or a systemd timer) to install the schedule.
- Keep logs in a known path and monitor failures.
- Validate in CI with `--dry-run` before deploy.

## Permissions Note

CIDER sync is metadata sync only. It does not grant user permissions directly. Permission mapping still relies on your authentication/group workflow.

