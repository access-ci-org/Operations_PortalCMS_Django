# Portal CMS Django agent instructions

## Purpose and boundaries

This repository contains the ACCESS Operations Portal Django CMS application: its django
CMS pages and versioning workflow, authentication, resource-provider permissions,
integration and infrastructure news, CIDER-backed resource views, and templates. The Git
root is this directory; `manage.py` and the Django project live under
`operations_portalcms_django/`, with the settings package at
`operations_portalcms_django/operations_portalcms_django/`.

Application code belongs here. Provisioning, deployed configuration, service units,
release selection, and production operations belong to
`../Operations_CMS_Infrastructure`. Local integrated environments are managed by
`../Operations_Django_Development`.

## Sources of truth and coupling

- `README.md` and `dev_documentation/CURRENT_STATE.md` describe the supported stack,
  setup, permissions, and current operational state. Do not copy release or dependency
  versions into durable guidance.
- The settings package under `operations_portalcms_django/operations_portalcms_django/`
  is the configuration authority; it reads external config (`portalcms_django_config`,
  `portal.*.json`). Never commit a real config or hardcode credentials or secret keys.
- Root `urls.py` and the CMS page/versioning workflow are the public route and content
  authority; removing or renaming routes can break external consumers and published
  pages.
- `portal/`, `infrastructure_news/`, `integration_news/`, and `resources/` each own their
  models, migrations, admin, and views. `resources/` is coupled to upstream CIDER
  schemas.
- Authentication is CILogon/OAuth2 with COmanage group sync driving resource-provider
  permissions. Treat authentication, permissions, and group mapping as high-risk shared
  interfaces.
- `access_django_user_admin` (from `../ACCESS_Django_user_app_pypi`) is an external
  dependency; a change to its public interface or pinned version is a producer/consumer
  boundary. See `multi_agent_plan.md` at the workspace root for the wiring.

## Safe inspection and validation

Always begin at the Git root:

```bash
git status --short --untracked-files=all
git diff --check
```

Run Django commands from `operations_portalcms_django/`, where `manage.py` lives, and only
with a deliberately nonproduction config. Use the smallest relevant checks:

```bash
python manage.py check
python manage.py test <affected_app>
python manage.py makemigrations --check --dry-run
```

Do not run checks or tests if the supplied config could reach the production PostgreSQL
database or live OAuth. Record missing configuration as a skipped check rather than
inventing values.

## Safety and change control

- A human must approve migrations, production data access, dependency changes,
  authentication or permission changes, public route or published-content changes,
  releases, pushes, merges, and tags.
- Never run `migrate`, an unbounded `makemigrations`, a production management command, or
  a deployment. Use `makemigrations --check --dry-run` for validation.
- Never commit config containing secret keys, database credentials, or OAuth client
  secrets, and do not commit `backups/`, `media/`, `static`/`staticfiles` build output,
  `var/`, or local virtual environments.
- Treat settings, root URLs, migrations, authentication, COmanage group sync, and the CMS
  versioning workflow as high-risk shared interfaces.

## Worktree and multi-agent rules

Inspect the full dirty state before editing and preserve unrelated tracked and untracked
files. Never reset, clean, or overwrite user work. Use one writer per repository or
isolated worktree; assign a single owner to migrations, root settings and URLs, and
dependency metadata. Infrastructure and consumer reviewers stay read-only until the
interface is frozen.

Every delegated task must state the repository root and base commit, the role and allowed
write paths, prohibited paths and external actions, the frozen API/schema/auth interfaces
and dependent repositories, the required validation checks, and the expected handoff. The
handoff must list files changed, the final diff summary, checks run and their results,
failures or skipped checks, assumptions, and unresolved risks.

## Wiring

See `multi_agent_plan.md` at the workspace root. Coupled repositories:
`Operations_CMS_Infrastructure` (deploys this app), `Operations_Django_Development` (local
harness), and `ACCESS_Django_user_app_pypi` (`access_django_user_admin`, producer).
