# Current Project State

Last verified: 2026-06-18 UTC.

## 2026-06-18 Update

- **Bug fix — `db_table` mismatch on plugin models:** `SystemStatusNewsItemPlugin` and `IntegrationNewsItemPlugin` were missing explicit `db_table` in their `Meta`, causing Django to auto-generate `<app_label>_<modelname>` names that didn't match the actual DB tables. This produced `ProgrammingError: relation "..." does not exist` when deleting users (cascade) or rendering CMS plugin pages. Fixed by adding explicit `db_table` to both models.

- **Table rename — `portal_*` prefix:** All 7 application tables in `infrastructure_news` and `integration_news` were renamed from `operations_portalcms_django_*` to the simpler `portal_*` convention matching their origin. New migrations `0002`, `0003`, `0004` added to both apps. No data loss; all FK constraints preserved.

  | Old name | New name |
  |---|---|
  | `operations_portalcms_django_systemstatusnews` | `portal_systemstatusnews` |
  | `operations_portalcms_django_systemstatusnewsitemplugin` | `portal_systemstatusnewsitemplugin` |
  | `operations_portalcms_django_systemstatusnews_affected_infrastructure_items` | `portal_systemstatusnews_affected_infrastructure_items` |
  | `operations_portalcms_django_integrationnews` | `portal_integrationnews` |
  | `operations_portalcms_django_integrationnewsitemplugin` | `portal_integrationnewsitemplugin` |
  | `operations_portalcms_django_integrationnews_affected_elements` | `portal_integrationnews_affected_elements` |
  | `operations_portalcms_django_integrationelement` | `portal_integrationelement` |

- **Migration state drift resolved:** `help_text` additions and `cmsplugin_ptr` parent-link attribute drift (pre-existing since app split) resolved by auto-generated `0004` state-correction migrations in both apps (no DDL).

- **Colleagues:** after `git pull`, run `migrate` before starting the app. The conditional `DO $$` block in `0003` is safe on both production-history DBs and fresh databases.

- `manage.py check`: 0 issues. `makemigrations --check`: no drift. `migrate --check`: no pending.
- Applied migration rows: 218 (previous 210 + 4 new infra_news + 4 new integ_news).

---

This snapshot records the current state observed from the deployed runtime config, the Django app, and read-only checks against the database of record.

## Runtime

- Database of record: Amazon RDS `portal1`
- RDS host: `opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com`
- Database owner: `portal_owner`
- Django database user/schema: `portal_django` / `portal_django`
- PostgreSQL search path: `"$user",public`
- PostgreSQL SSL mode: `require`
- Active config path: `/soft/django-cms-01/conf/portal.conf.dev.json`
- Active service/socket: `portal.service` / `/soft/django-cms-01/run/portal.socket`
- Public nginx host in this repo config: `cms2.operations.access-ci.org`
- Static root from deployed config: `/soft/django-cms-01/www/static`
- Media root from Django settings: repo `media/`; nginx serves `/soft/django-cms-01/tags/Operations_PortalCMS_Django/operations_portalcms_django/media/`
- Deployed dev config resolves `DEBUG=True` when no shell override is present.
- Development server banner: enabled, label `DEVELOPMENT SERVER`.
- Logging with `DEBUG=True`: app and Django logs go to Gunicorn stdout/stderr and then journald. App logger level is `INFO`; Django logger level is `WARNING`.

## Application

- Python requirement: `>=3.12,<3.13`
- Django: `>=5.2,<5.3`
- django CMS: `>=5.0,<5.1`
- django CMS versioning: installed and active
- django CMS moderation: not enabled
- Authentication: django-allauth CILogon provider plus local Django auth backend
- Package manager: `uv`
- Runtime config contract: Django exits during startup if `APP_CONFIG` is missing or cannot load JSON. `APP_ERROR_LOG` is no longer a required or accepted config key; the error log path is derived automatically from `APP_LOG`.
- Public pages render the bright-red `DEVELOPMENT SERVER` marker from `templates/base.html`.

## Application Structure

- `portal`: shared CMS/runtime glue, unprivileged view, CMS versioning workflow helpers, permissions utilities, and toolbar integration.
- `resources`: CIDER cache models, infrastructure/software special views, resource listing/detail behavior, and Operations API service-layer access.
- `infrastructure_news`: system status news models, forms, views, workflow transitions, admin registration, import tooling, and CMS plugins.
- `integration_news`: integration roadmap/software news models, forms, views, workflow transitions, admin registration, and CMS plugins.
- `templates`: shared base layout plus CMS/special-view templates; public pages use `templates/base.html`.
- `static` and `media`: static assets collected for nginx and user-uploaded/media content served from the repo media path.
- `database`: hands-on RDS inspection, dump, restore, and verification scripts; not official infrastructure automation.
- All news models were moved out of `portal` into feature apps on May 8, 2026. The migrations preserve existing database tables through explicit `db_table` settings.

## Database Verification

Read-only `database/verify_db.sh` against RDS `portal1` reported:

- Database size: 14 MB
- Application schema target: `portal_django`
- Application tables: 66
- Sequences: 45
- Applied migration rows: 210 (206 baseline + portal/0018 + resources/0001 + infrastructure_news/0001 + integration_news/0001)
- Ownership: all application tables owned by `portal_django`
- Unapplied migrations: 0
- Model migration drift: none (`makemigrations --check --dry-run` reported no changes)
- Migration plan: none (`migrate --plan` reported no planned operations)

Key row counts:

| Item | Count |
|------|------:|
| Users | 18 |
| Django groups | 23 |
| CMS pages | 18 |
| CMS page contents | 18 |
| CMS page permissions | 9 |
| CMS versions | 26 |
| System Status News | 249 |
| Integration News | 25 |
| Integration elements | 9 |
| CIDER infrastructure | 81 |
| CIDER organizations | 24 |
| CIDER feature categories | 14 |
| CIDER groups | 26 |

Workflow/content state:

- System Status News: 249 `published`
- Integration News: 24 `published`, 1 `pending_review`
- CMS versions: 18 `published`, 8 `unpublished`
- CIDER infrastructure by type: 34 `Compute`, 39 `Online Service`, 8 `Storage`
- Latest stored CIDER infrastructure `updated_at`: 2026-03-09 19:45:00.526000 UTC

## CMS Pages

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

## Focus-Area Permissions

Current page-level permission records:

| Page | Group | Change | Publish | Grant |
|------|-------|--------|---------|-------|
| Student Training and Engagement Program | `Focus_area_editors` | yes | yes | page and descendants |
| Student Training and Engagement Program | `Focus_STEP_Editors` | yes | no | page and descendants |
| CyberSecurity | `Focus_area_editors` | yes | yes | page and descendants |
| CyberSecurity | `Focus_Cybersecurity_Editors` | yes | no | page and descendants |
| Operational Support | `Focus_area_editors` | yes | yes | page and descendants |
| Operational Support | `Focus_operationsSupport_Editors` | yes | no | page and descendants |
| Data Transfer and Networking Support | `Focus_area_editors` | yes | yes | page and descendants |
| Data Transfer and Networking Support | `Focus_Networking_dataTransfer_Editors` | yes | no | page and descendants |
| Operations Portal Home | `Home_page_editors` | yes | yes | page only |

The focus-area workflow is therefore currently reviewer/publisher capable for `Focus_area_editors`, and edit-only for the page-specific focus-area groups.

## CIDER Sync State

`sync_cider_from_api` completed successfully against the Operations API on 2026-04-24.

API results fetched:

- Infrastructure: 78
- Groups: 26
- Organizations: 21
- Feature categories: 14
- Features: 54

Write impact from the initial metadata refresh:

- 78 infrastructure rows updated
- 26 group rows updated
- 21 organization rows updated
- 14 feature category rows updated

A follow-up group-prune sync deleted 2 stale local CIDER group rows that were not present in the CIDER API:

- `rp.ncsa.illinois.edu`
- `rp.sdsc.edu`

Current group-cache result:

- `cider_groups`: 26 rows
- current CIDER API groups: 26
- local-only groups: none
- API-only groups: none
- explicit stale-group prune dry-run: `groups_would_delete: 0`

The local RDS tables still contain more CIDER infrastructure and organization rows than the latest API response. The current sync command updates or creates rows, and stale-group pruning is now available explicitly through `--prune-stale-groups`.

## RP Permission Sync Caveat

The current Django auth group table still contains the older five RP-style group pairs plus three global operations URN groups:

- `rp.access-ci.org`
- `rp.ncsa.illinois.edu`
- `rp.psc.edu`
- `rp.sdsc.edu`
- `rp.tacc.utexas.edu`
- `operations.access-ci.org:concierge`
- `operations.access-ci.org:badge.maintainer`
- `operations.access-ci.org:roadmap.maintainer`

The current `cider_groups` table contains 26 current CIDER API records, all with `resource-catalog.access-ci.org` group type. Examples include `bridges2.psc.access-ci.org`, `stampede3.tacc.access-ci.org`, and `anvil.purdue.access-ci.org`.

Do not blindly run `setup_rp_permissions` against the database of record without deciding whether those CIDER group IDs should all become login authorization groups. The command is idempotent and now supports `--dry-run`, but the real run writes Django groups and permissions.

Current dry-run after pruning:

- selected CIDER groups: 26
- unfiltered auth setup would create 52 permissions and 52 auth groups
- unfiltered auth setup would add 52 group-permission links
- no auth groups were created during this pass

## Current Health Snapshot

- Django system checks: clean.
- Deployment checks: known production-hardening warnings remain and are tracked under Open Security Items.
- Database: RDS `portal1` reachable; schema, ownership, row counts, and sequence checks passed.
- Migrations: no unapplied migrations, no model drift, and no planned migration operations.
- CIDER sync dry-runs: current API metadata was inspected; stale-group prune reports no remaining group deletions.
- RP permission dry-run: selected 26 current CIDER groups and would create auth objects if run for real; no writes were made during inspection.
- Static assets: dry-run completed with the known duplicate `admin/img/search.svg` destination.
- Smoke check: `/integration-news/` returned HTTP 200 and rendered the development-server banner.
- Repo-level scripts under `tests/` can create or modify users, groups, and news records; run them only against a disposable clone or an approved maintenance window.

---

## APP_CONFIG Contract

`APP_CONFIG` is the single required environment variable. Django exits at startup if it is missing or cannot parse as JSON.

On this server the active config is `/soft/django-cms-01/conf/portal.conf.dev.json`. It carries the Django secret, database connection details, allowed hosts, logging path, OAuth/CILogon credentials, and optional runtime behavior such as `DEBUG`, the development-server banner, and API base URLs.

`APP_ERROR_LOG` is no longer accepted; the error log path is derived automatically from the application log path.

---

## Permission Systems

### 1. News Workflow Groups

Two-tier Author/Manager model per news type. Created by `manage.py setup_groups`.

| Group | Permissions |
|---|---|
| `System Status Authors` | create, edit; must submit for review to publish |
| `System Status Managers` | create, edit, delete, review, publish |
| `Integration News Authors` | create, edit; must submit for review to publish |
| `Integration News Managers` | create, edit, delete, review, publish |

Statuses: `draft` → `pending_review` → `approved` → `published` (or `rejected`).

Django permission codenames: `can_review_systemstatusnews`, `can_publish_systemstatusnews`, `can_review_integrationnews`, `can_publish_integrationnews`.

### 2. Focus Area Page Workflow

CMS versioning-based draft/publish. Created by `manage.py setup_focus_area_page_permissions`.

| Group | Role |
|---|---|
| `Focus_area_editors` | Can change and publish any focus area page |
| `Focus_STEP_Editors` | Can change STEP pages (edit only, no publish) |
| `Focus_Cybersecurity_Editors` | Can change Cybersecurity pages (edit only) |
| `Focus_operationsSupport_Editors` | Can change Operational Support pages (edit only) |
| `Focus_Networking_dataTransfer_Editors` | Can change Networking pages (edit only) |
| `Home_page_editors` | Can change and publish the home page |

Workflow: editor creates draft → submits for review → `Focus_area_editors` approves and publishes.

### 3. RP Permissions (optional)

Automatic news access for Resource Provider coordinators based on CIDER group membership. Created by `manage.py setup_rp_permissions`.

**Caution:** the current `auth_group` table contains older RP-style group names (`rp.ncsa.illinois.edu`, etc.) alongside 26 current CIDER groups. Do not run `setup_rp_permissions` without reviewing which CIDER group IDs should become login-authorization groups. The command supports `--dry-run`.

## Maintenance Commands To Know

- `manage.py setup_groups`: creates/updates news workflow author and manager groups.
- `manage.py setup_focus_area_page_permissions`: creates/updates focus-area CMS page workflow groups and page permissions.
- `manage.py setup_rp_permissions`: maps current CIDER RP groups into Django auth groups and permissions; dry-run first.
- `manage.py sync_cider_from_api`: refreshes CIDER infrastructure, organization, group, category, and feature metadata.
- `manage.py sync_cider_from_api --skip-infrastructure --prune-stale-groups`: checks or prunes stale local CIDER group rows.
- `database/verify_db.sh`: read-only RDS schema, ownership, count, and migration-state verification.

---

## Open Security Items

Items from `manage.py check --deploy` not yet resolved — noted for future production hardening:

- `SECURE_HSTS_SECONDS` not set — enable only after confirming full HTTPS coverage
- `SECURE_SSL_REDIRECT` not `True` — handled by nginx; set this if nginx redirect is removed
- `SECRET_KEY` quality warning — replace with a long random value before production
- `SESSION_COOKIE_SECURE` not `True`
- `CSRF_COOKIE_SECURE` not `True`
- `DEBUG = True` in deployed config — intentional for dev; must be `False` in production
- `X_FRAME_OPTIONS` not `DENY` — django CMS requires framing; assess before changing

Additional open items:

- **Resource/API HTML rendering** — CIDER/API descriptions in resource templates are escaped and rendered with line breaks; remaining `|safe` uses are limited to trusted form help text and should stay that way.
- **News state transitions** — workflow state-changing endpoints require POST, and list-page controls submit CSRF-protected forms.
- **External assets** — Bootstrap and ACCESS UI loaded from CDN. Pin versions or self-host for production.

---

## Runtime Transition Checklist

Steps 1–3 complete. Steps 4–6 remain:

- [x] 1. Stabilise manual dev server on `cms2`
- [x] 2. Shared repository ownership (`appdev` group, `g+w`)
- [x] 3. Align manual Django management commands (`manage.prod.sh.j2`)
- [ ] 4. Prepare `software` user handoff — create `software` OS user, transfer ownership of `/soft/django-cms-01/` tree
- [ ] 5. Introduce infra-managed model — Ansible renders `portal.conf` from vaulted deployment variables; systemd `APP_CONFIG` points at rendered file
- [ ] 6. Careful cutover — retire manual `portal_django` user workflow; `software` user owns the service

**Definition of done:** the portal service runs under the `software` user, config is rendered by Ansible, no manual `portal_django` session is required for normal operation.
