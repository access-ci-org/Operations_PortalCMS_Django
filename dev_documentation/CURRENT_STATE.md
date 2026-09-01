# Current Project State

Last verified: 2026-06-26 UTC.

This document is the living operational map for the ACCESS Operations Portal
CMS. It describes the current runtime, code structure, data model, workflow
logic, operational commands, and known risks. It is intentionally not a
changelog; date-sensitive counts and observations are grouped under
Current Verification Snapshot.

## Current Snapshot

- The portal is a Django 5.2 / django CMS 5 application managed with `uv` and
  served through Gunicorn/nginx.
- The database of record is Amazon RDS `portal1`; the Django application role
  and schema are both `portal_django`.
- Runtime configuration is loaded from the JSON file named by `APP_CONFIG`.
  The deployed dev config is `/soft/django-cms-01/conf/portal.conf.dev.json`.
- The deployed dev environment currently resolves `DEBUG=True` and renders the
  public development-server banner.
- The code is organized around `portal` for shared CMS/runtime behavior,
  `resources` for CIDER-backed resource views, `infrastructure_news` for System
  Status News, and `integration_news` for Integration News.
- News data lives in the feature apps and uses stable `portal_*` table names
  through explicit `db_table` settings and migration state.
- Django system checks, migration checks, and database verification were clean
  at the last verification.
- Known remaining work is production hardening, careful RP permission sync
  review, and the runtime handoff from the manual `portal_django` workflow to
  the planned `software` user / infra-managed model. This refers specifically
  to the Django systemd service running as `software` (checklist items 4-6
  below) — the `software` OS account itself already exists and already runs
  backup/retrieval/restore operations today (see
  `../database/README.md`), independent of that still-pending service
  cutover.

## Runtime & Deployment

### Runtime Stack

- Python requirement: `>=3.12,<3.13`
- Django: `>=5.2,<5.3`
- django CMS: `>=5.0,<5.1`
- django CMS versioning: installed and active
- django CMS moderation: not enabled
- Authentication: django-allauth CILogon provider plus local Django auth backend
- Package manager: `uv`
- WSGI/service layer: Gunicorn behind nginx

### Active Deployment

- Database of record: Amazon RDS `portal1`
- RDS host: `opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com`
- Database owner: `portal_owner`
- Django database user/schema: `portal_django` / `portal_django`
- PostgreSQL search path: `"$user",public`
- PostgreSQL SSL mode: `require`
- Active config path: `/soft/django-cms-01/conf/portal.conf.dev.json`
- Active service/socket: `portal.service` /
  `/soft/django-cms-01/run/portal.socket`
- Public nginx host in this repo config: `cms2.operations.access-ci.org`
- Static root from deployed config: `/soft/django-cms-01/www/static`
- Media root from Django settings: repo `media/`; nginx serves
  `/soft/django-cms-01/tags/Operations_PortalCMS_Django/operations_portalcms_django/media/`

### Runtime Config Contract

`APP_CONFIG` is the required entry point. Django exits during startup if
`APP_CONFIG` is missing, cannot load JSON, or lacks required keys.

Required JSON keys:

- `DJANGO_SECRET_KEY`
- `APP_LOG`

`APP_CONFIG` values are authoritative for runtime settings. Environment
variables remain compatibility fallbacks only when a key is absent from the JSON
config. The error log path is derived from `APP_LOG` and is not part of the
required config contract.

Optional runtime behavior comes from the same config/environment path,
including `DEBUG`, the environment/development banner, allowed hosts, OAuth
credentials, database settings, logging location, and API base URLs.

For local development, copy `dev_documentation/portal.local.example.json` to
`portal.conf.dev.json` at the repository root and fill in your local database
password and secret key before running `uv run python manage.py`.

### Logging

- With `DEBUG=True`, app and Django logs go to Gunicorn stdout/stderr and then
  journald.
- With `DEBUG=False`, logs use rotating file handlers based on `APP_LOG` and
  the derived error log path.
- App logger level is `INFO`; Django logger level is `WARNING`.

## Application Structure

- `operations_portalcms_django`: Django settings, root URL routing, WSGI, and
  ASGI project package.
- `portal`: shared CMS/runtime glue, unprivileged view, CMS versioning workflow
  helpers, permission utilities, toolbar integration, and shared management
  commands.
- `resources`: CIDER cache models, infrastructure/software special views,
  resource listing/detail behavior, and Operations API service-layer access.
- `infrastructure_news`: System Status News models, forms, views, workflow
  transitions, admin registration, import tooling, and CMS plugins.
- `integration_news`: Integration News and integration-element models, forms,
  views, workflow transitions, admin registration, and CMS plugins.
- `templates`: shared base layout plus CMS and special-view templates. Public
  pages use `templates/base.html`.
- `static` and `media`: source static assets and user-uploaded/media content.
- `database`: hands-on RDS inspection, dump, restore, and verification scripts.
  These are operational tools, not official infrastructure automation.
- `operations_portalcms_django/tests`: standalone integration/check scripts.
  Some scripts create or modify users, groups, and news records; run them only
  against a disposable clone or during an approved maintenance window.

## Routing & Public Surfaces

Root URL routing mounts the app-specific URLconfs before the django CMS
catch-all route.

| Surface | Route(s) | Source |
|---|---|---|
| Django admin | `/admin/` | `operations_portalcms_django.urls` |
| Filer | `/filer/` | `operations_portalcms_django.urls` |
| Auth/CILogon | `/accounts/` | django-allauth |
| ACCESS user admin | `/access_django_user_admin/` | `access_django_user_admin` |
| Resource listings | `/resources/access-allocated/`, `/resources/access-online-services/` | `resources.urls` |
| Software discovery | `/resources/software-discovery/`, `/resources/software/<software_id>/` | `resources.urls` |
| Resource detail | `/node/<node_id>/` | `resources.urls` |
| System Status News | `/infrastructure-news/` plus add/update/workflow routes | `infrastructure_news.urls` |
| Integration News | `/integration-news/` plus add/update/workflow routes | `integration_news.urls` |
| Permission fallback | `/unprivileged/` | `portal.urls` |
| CMS page workflow helpers | `/cms-versioning/version/<version_id>/submit-for-review/`, `/unlock/` | `portal.urls` |
| CMS pages | catch-all route | `cms.urls` |

The django CMS catch-all route stays last so explicit app routes resolve before
CMS page lookup.

## Data Model & Database Tables

### News Tables

System Status News is owned by `infrastructure_news`:

| Model / relationship | Current table |
|---|---|
| `SystemStatusNews` | `portal_systemstatusnews` |
| `SystemStatusNewsItemPlugin` | `portal_systemstatusnewsitemplugin` |
| affected infrastructure M2M | `portal_systemstatusnews_affected_infrastructure_items` |

Integration News is owned by `integration_news`:

| Model / relationship | Current table |
|---|---|
| `IntegrationNews` | `portal_integrationnews` |
| `IntegrationNewsItemPlugin` | `portal_integrationnewsitemplugin` |
| `IntegrationElement` | `portal_integrationelement` |
| affected elements M2M | `portal_integrationnews_affected_elements` |

The feature-app split is represented in code by `infrastructure_news` and
`integration_news`; table names remain stable through explicit model
`db_table` settings and migration state.

### CIDER Cache Tables

| Model | Current table | Role |
|---|---|---|
| `CiderInfrastructure` | `cider_infrastructure` | Infrastructure resources, status, affiliations, and descriptions |
| `CiderOrganizations` | `cider_organizations` | Sites and institutions |
| `CiderFeatures` | `cider_features` | Feature categories and feature metadata |
| `CiderGroups` | `cider_groups` | Resource Provider groups used by optional permission sync |

### CMS And Auth Tables

django CMS, djangocms-versioning, django-allauth, Django auth, sessions, filer,
and thumbnail tables remain managed by their respective apps. Page-level focus
area permissions are stored in django CMS permission tables and managed by the
focus-area setup command.

## Workflow & Permission Logic

### News Workflow

Both news apps use the same status model:

`draft` -> `pending_review` -> `approved` -> `published`

Items may also move to `rejected`; published items can be unpublished back to
`draft` by the author or a superuser.

Workflow state-changing endpoints require login and POST. Review and publish
actions require the app-specific custom permissions:

| News type | Review permission | Publish permission |
|---|---|---|
| System Status News | `infrastructure_news.can_review_systemstatusnews` | `infrastructure_news.can_publish_systemstatusnews` |
| Integration News | `integration_news.can_review_integrationnews` | `integration_news.can_publish_integrationnews` |

Two-tier author/manager groups are created by `manage.py setup_groups`:

| Group | Role |
|---|---|
| `System Status Authors` | create and edit; submit for review to publish |
| `System Status Managers` | create, edit, delete, review, and publish |
| `Integration News Authors` | create and edit; submit for review to publish |
| `Integration News Managers` | create, edit, delete, review, and publish |

### Focus-Area Page Workflow

Focus-area pages use django CMS versioning. Their setup is split across two
commands: `manage.py setup_groups` creates the focus-area auth groups and grants
shared CMS/plugin permissions, while `manage.py setup_focus_area_page_permissions`
creates or updates the CMS `PagePermission` rows for the focus pages.

| Group | Role |
|---|---|
| `Focus_area_editors` | Can change and publish any focus-area page |
| `Focus_STEP_Editors` | Can change STEP pages; edit only |
| `Focus_Cybersecurity_Editors` | Can change Cybersecurity pages; edit only |
| `Focus_operationsSupport_Editors` | Can change Operational Support pages; edit only |
| `Focus_Networking_dataTransfer_Editors` | Can change Networking pages; edit only |
| `Home_page_editors` | Can change and publish the home page |

Current intended flow: page-specific editor creates a draft, submits it for
review, and a `Focus_area_editors` member reviews/publishes.

### RP Permission Sync

`manage.py setup_rp_permissions` can map CIDER Resource Provider groups into
Django auth groups and permissions. Treat this as optional and review the
selected CIDER groups before a real run.

The current auth group table still contains older RP-style groups alongside
current CIDER group records. The command is idempotent and supports `--dry-run`,
but a real run writes Django groups, permissions, and group-permission links.

## Operational Commands

Run Django management commands from the Django project directory
`operations_portalcms_django/` or through the deployed management wrapper.

| Command | Current use |
|---|---|
| `manage.py setup_groups` | Creates/updates news author/manager groups; creates focus-area auth groups; grants shared CMS/plugin/page permissions; gives `Focus_area_editors` publish/unlock rights; removes publish from page-specific focus groups |
| `manage.py setup_focus_area_page_permissions` | Creates/updates CMS `PagePermission` rows for focus pages after the groups exist; supports `--dry-run` |
| `manage.py setup_rp_permissions` | Maps selected CIDER RP groups into Django auth groups and permissions; dry-run before any real run |
| `manage.py sync_cider_from_api` | Refreshes CIDER infrastructure, organization, group, category, and feature metadata; supports `--dry-run` |
| `manage.py sync_cider_from_api --skip-infrastructure --prune-stale-groups` | Checks or prunes stale local CIDER group rows |
| `manage.py import_drupal_news` | One-time Drupal cutover importer for both news feeds; accepts normalized JSON or a raw gzip/plain MySQL dump, requires an explicit current/future Infrastructure News cutoff for replacement, and supports strict dry-run, guarded atomic replacement, source checksum/count confirmation, relationship validation, and markdown reporting |
| `database/verify_db.sh` | Read-only RDS schema, ownership, count, and migration-state verification |

After pulling changes that include migrations, run `migrate` before starting the
app. Current migration state preserves existing data and table names; the
conditional table-rename migration path is safe for both production-history
databases and fresh databases.

## Current Verification Snapshot

The facts in this section are date-sensitive and tied to the Last verified date
at the top of the document.

### Health

- Django system checks: clean.
- Deployment checks: known production-hardening warnings remain and are tracked
  under Open Security / Transition Items.
- Database: RDS `portal1` reachable; schema, ownership, row counts, and sequence
  checks passed.
- Migrations: no unapplied migrations, no model drift, and no planned migration
  operations.
- Applied migration rows: 216.
- Static assets: dry-run completed with the known duplicate
  `admin/img/search.svg` destination.
- Smoke check: `/integration-news/` returned HTTP 200 and rendered the
  development-server banner.

### Database Counts

| Item | Count |
|---|---:|
| Application tables | 66 |
| Sequences | 45 |
| Users | 19 |
| Django groups | 23 |
| CMS pages | 18 |
| CMS page contents | 18 |
| CMS page permissions | 9 |
| CMS versions | 28 |
| System Status News | 249 |
| Integration News | 25 |
| Integration elements | 9 |
| CIDER infrastructure | 81 |
| CIDER organizations | 24 |
| CIDER feature categories | 14 |
| CIDER groups | 26 |

Workflow/content state:

- System Status News: 238 `published`, 11 `draft`
- Integration News: 15 `published`, 9 `draft`, 1 `pending_review`
- CMS versions: 18 `published`, 8 `unpublished`, 2 `draft`
- CIDER infrastructure by type: 34 `Compute`, 39 `Online Service`, 8 `Storage`
- Latest stored CIDER infrastructure `updated_at`:
  2026-04-16 01:41:39.492000+00:00

### CMS Pages

Current English CMS page titles:

- Operations Portal Home
- Public Content
- ACCESS Ticket System FAQs
- ACCESS Identity Management - Frequently Asked Questions
- About ACCESS Operations
- ACCESS Integration and Operations Help
- ACCESS Infrastructure Integration
- Infrastructure Location Map
- Infrastructure Maps
- CONECT Map
- Infrastructure Timelines
- Infrastructure Production Timeline
- Focus Areas
- CyberSecurity
- Cybersecurity Awareness Resources
- Data Transfer and Networking Support
- Operational Support
- Student Training and Engagement Program

### Focus-Area Page Permissions

| Page | Group | Change | Publish | Grant |
|---|---|---|---|---|
| Student Training and Engagement Program | `Focus_area_editors` | yes | yes | page and descendants |
| Student Training and Engagement Program | `Focus_STEP_Editors` | yes | no | page and descendants |
| CyberSecurity | `Focus_area_editors` | yes | yes | page and descendants |
| CyberSecurity | `Focus_Cybersecurity_Editors` | yes | no | page and descendants |
| Operational Support | `Focus_area_editors` | yes | yes | page and descendants |
| Operational Support | `Focus_operationsSupport_Editors` | yes | no | page and descendants |
| Data Transfer and Networking Support | `Focus_area_editors` | yes | yes | page and descendants |
| Data Transfer and Networking Support | `Focus_Networking_dataTransfer_Editors` | yes | no | page and descendants |
| Operations Portal Home | `Home_page_editors` | yes | yes | page only |

The focus-area workflow is reviewer/publisher capable for
`Focus_area_editors`, and edit-only for the page-specific focus-area groups.

### CIDER Sync State

`sync_cider_from_api` completed successfully against the Operations API on
2026-04-24.

API results fetched:

- Infrastructure: 78
- Groups: 26
- Organizations: 21
- Feature categories: 14
- Features: 54

Write impact from the metadata refresh:

- 78 infrastructure rows updated
- 26 group rows updated
- 21 organization rows updated
- 14 feature category rows updated

A follow-up group-prune sync removed stale local CIDER group rows that were not
present in the CIDER API:

- `rp.ncsa.illinois.edu`
- `rp.sdsc.edu`

Current group-cache result:

- `cider_groups`: 26 rows
- Current CIDER API groups: 26
- Local-only groups: none
- API-only groups: none
- Explicit stale-group prune dry-run: `groups_would_delete: 0`

The local RDS tables still contain more CIDER infrastructure and organization
rows than the latest API response. The current sync command updates or creates
rows; stale-group pruning is available explicitly through
`--prune-stale-groups`.

### RP Permission Dry-Run

The current Django auth group table still contains the older five RP-style group
pairs plus three global operations URN groups:

- `rp.access-ci.org`
- `rp.ncsa.illinois.edu`
- `rp.psc.edu`
- `rp.sdsc.edu`
- `rp.tacc.utexas.edu`
- `operations.access-ci.org:concierge`
- `operations.access-ci.org:badge.maintainer`
- `operations.access-ci.org:roadmap.maintainer`

The current `cider_groups` table contains 26 current CIDER API records, all with
`resource-catalog.access-ci.org` group type. Examples include
`bridges2.psc.access-ci.org`, `stampede3.tacc.access-ci.org`, and
`anvil.purdue.access-ci.org`.

Current dry-run after pruning:

- Selected CIDER groups: 26
- Unfiltered auth setup would create 55 permissions
- Unfiltered auth setup would create 52 auth groups and update 3 existing auth groups
- Unfiltered auth setup would add 55 group-permission links
- No auth groups were created during this pass

## Open Security / Transition Items

### Production Hardening

Items from `manage.py check --deploy` remain open for a future production
configuration:

- `SECURE_HSTS_SECONDS` not set; enable only after confirming full HTTPS coverage
- `SECURE_SSL_REDIRECT` not `True`; nginx currently handles redirect behavior
- `SECRET_KEY` quality warning; replace with a long random value before
  production
- `SESSION_COOKIE_SECURE` not `True`
- `CSRF_COOKIE_SECURE` not `True`
- `DEBUG = True` in deployed config; intentional for dev and must be `False` in
  production
- `X_FRAME_OPTIONS` not `DENY`; django CMS requires framing, so assess before
  changing

Additional open items:

- Resource/API HTML rendering escapes CIDER/API descriptions and renders line
  breaks. Remaining `|safe` uses are limited to trusted form help text and
  should stay that way.
- News state transitions require POST, and list-page controls submit
  CSRF-protected forms.
- External assets load Bootstrap and ACCESS UI from CDN. Pin versions or
  self-host for production.

### Runtime Transition Checklist

Steps 1-3 are complete. Steps 4-6 remain:

- [x] 1. Stabilize manual dev server on `cms2`
- [x] 2. Shared repository ownership (`appdev` group, `g+w`)
- [x] 3. Align manual Django management commands (`manage.prod.sh.j2`)
- [ ] 4. Prepare `software` user handoff: create `software` OS user and
  transfer ownership of `/soft/django-cms-01/`. As of 2026-08-14, `/soft/django-cms-01/`
  is already `software`-owned and `software` already runs backup, retrieval, and
  restore operations there (see `../database/README.md`); confirm whether this item
  should now be checked off, or whether it still tracks unfinished work beyond OS
  ownership (e.g. a formal handoff sign-off).
- [ ] 5. Introduce infra-managed model: Ansible renders `portal.conf` from
  vaulted deployment variables, and systemd `APP_CONFIG` points at the rendered
  file
- [ ] 6. Carefully cut over: retire manual `portal_django` user workflow;
  `software` user owns the service

Definition of done: the portal service runs under the `software` user, config is
rendered by Ansible, and no manual `portal_django` session is required for
normal operation.
