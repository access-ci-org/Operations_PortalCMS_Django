# Current Application State

Repository behavior reviewed: 2026-11-06. The application and API descriptions
below were checked against the source tree. Live production settings, service
state, database counts, and external consumer behavior were not checked for this
update. The last recorded operational snapshot in the previous version was dated
2026-06-26; do not treat its counts or deployment details as current.

This document summarizes the app's structure, behavior, operational ownership,
and intended follow-up. It is not a changelog. Deployment configuration and
production operations belong to `Operations_CMS_Infrastructure`; local integrated
environments belong to `Operations_Django_Development`.

## Application Summary

- ACCESS Operations Portal is a Django CMS application with the `portal`,
  `resources`, `infrastructure_news`, and `integration_news` apps.
- Runtime configuration is external and selected through `APP_CONFIG`. Do not
  commit real configuration or credentials.
- Authentication uses Django/allauth with CILogon. CILogon does not own or sync
  Resource Provider group membership in this app.
- The application persists two news feeds and local CIDER cache data. Production
  database and service state must be confirmed from the authorized operations
  environment, not inferred from this source tree.

## Runtime and Deployment Ownership

- Supported stack and local setup are documented in [README.md](../README.md).
- `Operations_CMS_Infrastructure` owns deployed configuration, systemd/nginx,
  release selection, migrations, and service operations.
- Follow its deployment workflow and runbook for release and migration actions;
  do not treat a manual `manage.py migrate` as the deployment procedure.
- Runtime settings are loaded from the JSON file named by `APP_CONFIG`. The
  repository contains an example for local development; use local secret values
  only in ignored local configuration.
- Django and app logs go to the configured runtime logging destination. The
  exact destination depends on deployment configuration.

## Application Structure

- `portal`: shared CMS integration, page workflow helpers, auth adapters,
  permission utilities, and management commands.
- `resources`: CIDER-backed resource models, sync command, and resource/software
  views.
- `infrastructure_news`: System Status News models, forms, workflow, admin,
  import parser/command, and CMS plugins.
- `integration_news`: Integration News and integration-element models, forms,
  workflow, admin, and CMS plugins.
- `operations_portalcms_django`: project settings package, root URLs, ASGI, and
  WSGI. CMS URL handling is last in the root URL list so explicit app routes win.
- `templates`, `static`, and `media`: shared page templates, source assets, and
  uploaded CMS media.
- `database`: operator-oriented database and media backup/verification tools;
  these are separate from deployment automation.

## News Data and Workflow

The feature apps own their models while retaining stable table names:

| Model | Table |
|---|---|
| `SystemStatusNews` | `portal_systemstatusnews` |
| `IntegrationNews` | `portal_integrationnews` |
| `IntegrationElement` | `portal_integrationelement` |
| News CMS plugins and affected-item relationships | `portal_*` tables declared by the models |

Each feed has a `draft` or `published` status. There is no active review/pending
workflow in the app; reviewer fields remain in the models as stored metadata.
Publisher-group members can create drafts and may publish or unpublish with the
feed's custom publish permission. Editing requires the normal model change
permission. A non-superuser needs delete permission and may delete only their
own item; superusers can delete any item. State-transition endpoints require
POST.

New infrastructure and integration records without an external identifier are
assigned a unique ID starting at 2000, then above the current maximum. Supplied
IDs are preserved, and Django's primary key remains separate. This allocation
uses existing fields and does not require a schema migration.

The three news distribution choices are stored independently: email everyone,
email subscribers, and post to Slack. They express publishing intent; email and
Slack delivery are not implemented here. Older System Status delivery-control
fields remain separate from these choices.

## Public News Feeds (Current Source Behavior)

These are the app-side behaviors found in the current source. The outside script
that consumes them has not been reviewed here, so consumer compatibility should
not be inferred from this description. Treat any change to these paths or fields
as a separate contract review.

Both feeds are public JSON list views that accept GET and HEAD and cache responses
for 15 minutes. They include only active, published records and order newest
originally created records first. The returned `content` value is the stored news
content. Each record also includes the URL of its corresponding news page.

| Feed | Route(s) | Feed-specific fields and formatting |
|---|---|---|
| Infrastructure | `/api/infrastructure_news`, `/api/infrastructure_news_v2` | `subject`, `type`, `content`, `start_timestamp`, `end_timestamp`, `outage_id`, `distribution_options`, `affected_infrastructure`. Start/end timestamps are formatted in `America/Chicago` as `YYYY-MM-DDTHH:MM:SS±HHMM`; missing dates are empty strings. `outage_id` is a string or `null`. |
| Integration | `/api/integration_news` | `subject`, `type`, `content`, `effective_date`, `integration_news_id`, `distribution_options`, `affected_integration_element`. `effective_date` is an ISO date or an empty string. `integration_news_id` is a string or `null`. |

Affected infrastructure entries include the resource ID and, when locally
available, the resource title and latest status. Affected integration entries
contain element titles. Distribution choices are returned as a comma-separated
string. This section documents Django's current serialization only; it does not
claim the external consumer has been checked or accepts every field/value.

## CMS and Permission Workflows

Focus-area pages use django CMS versioning. `setup_groups` creates the focus-area
auth groups and shared CMS/plugin permissions; `setup_focus_area_page_permissions`
creates or updates page-specific `PagePermission` rows. Page-specific groups are
edit-only; `Focus_area_editors` can publish focus-area pages. The intended flow is
for a page-specific editor to prepare a draft and a `Focus_area_editors` member to
review and publish it.

Operations and Resource Provider groups are not speculatively provisioned by this
app. Resource Provider membership is owned centrally by the Warehouse/Operations
API, not CILogon; this app does not sync that membership during login. This app
does not automatically remove old per-RP auth groups from the database.

## Data Sources and Management Commands

- `sync_cider_from_api` refreshes the local CIDER infrastructure, organization,
  group, category, and feature metadata. It supports `--dry-run`; review the
  planned changes before a write run.
- `--prune-stale-groups` can delete local CIDER group rows missing from the
  fetched group set. It is optional, separate from routine sync, and should be
  previewed with `--dry-run` first. It does not prune infrastructure rows.
- `setup_groups` configures focus-area groups and shared CMS permissions;
  it does not manage the news publisher groups.
- `setup_focus_area_page_permissions` configures focus-page permissions and
  supports `--dry-run`.
- `import_drupal_news` is retained as one-time Drupal cutover tooling. It has a
  parser, a canonical management command, a portal compatibility entry point,
  tests, and a guarded plan/apply workflow. The Nov 6, 2026 read-only comparison
  of the Nov 5 and Nov 6 source dumps found no new news IDs or changed revisions.
  The command remains in the repository until final import/source retirement is
  confirmed; archive/removal is a separate cleanup decision. See
  [future_cleanup_plan.md](future_cleanup_plan.md).

Run Django commands from `operations_portalcms_django/` with a deliberately
nonproduction config unless an authorized human is following an approved
operational runbook.

## Verification and Open Operational Follow-up

No production database, runtime configuration, deployment service, or external
news consumer was accessed for this update. No Django commands or tests were run;
`git diff --check` passed.

The previous version recorded live counts, page titles, CIDER sync results,
security-check findings, and a runtime-user transition checklist. Those details
were dated and could not be confirmed from this source review, so they are not
presented as current facts here. Before relying on live state, an authorized
operator should refresh the relevant checks and confirm the deployment/runtime
handoff in the infrastructure runbook.

The previously recorded production-hardening topics included HTTPS and cookie
settings, `DEBUG`, frame policy compatibility with django CMS, and third-party
CDN assets. Their current status is unknown from this review; verify against the
intended production configuration before treating them as open or resolved.
