# Security Hardening Notes

Date: 2026-04-27

This document tracks future production and staging hardening work for the Operations Portal CMS. It is intentionally separate from `developer_Steps.md`, which is only for local `uv` setup against a restored `portal1` backup.

## Current Status

`uv run python manage.py check` passes in the current app configuration.

`uv run python manage.py check --deploy` still reports expected production hardening warnings for:

- HSTS
- HTTPS redirect
- placeholder or weak secret-key quality in sample/local configs
- secure session cookies
- secure CSRF cookies
- `X_FRAME_OPTIONS` not being `DENY`

These are not local-development blockers. They should be resolved deliberately for staging/production after proxy and CMS editing behavior are verified.

## Environment Config

Future staging/production configs should set:

- `DEBUG=false`
- explicit `ALLOWED_HOSTS`
- strong `DJANGO_SECRET_KEY`
- reviewed `APP_ENV`
- reviewed `PUBLIC_HOSTNAME`
- reviewed `ENVIRONMENT_BANNER_ENABLED`
- reviewed `ENVIRONMENT_LABEL`

Local configs should keep `DEBUG=true`, use local PostgreSQL, and avoid production proxy assumptions.

## Proxy And HTTPS Settings

Add APP_CONFIG-driven support before enabling production HTTPS hardening:

- `CSRF_TRUSTED_ORIGINS`
- `USE_X_FORWARDED_HOST`
- `USE_X_FORWARDED_PORT`
- a config key that maps deliberately to Django's `SECURE_PROXY_SSL_HEADER`

After nginx/Gunicorn HTTPS behavior is verified end to end, consider enabling:

- `SECURE_SSL_REDIRECT`
- `SESSION_COOKIE_SECURE`
- `CSRF_COOKIE_SECURE`
- HSTS, starting with a low `SECURE_HSTS_SECONDS`

Do not enable these blindly in local development.

## Clickjacking And CMS Editing

`X_FRAME_OPTIONS = 'SAMEORIGIN'` is currently intentional because Django CMS/admin editing flows may rely on same-origin framing behavior.

Before changing this to `DENY`, test:

- Django admin login
- CMS toolbar rendering
- page edit mode
- plugin edit/create workflows
- djangocms-versioning draft/publish workflow

## CSRF And State-Changing Actions

News workflow state transitions should be converted to POST-only actions with CSRF protection.

Current actions to review include:

- submit for review
- approve
- reject
- publish
- unpublish

The templates currently expose several of these as links. They should become forms or button actions that submit POST requests.

## External HTML Rendering

CIDER/API resource descriptions are currently rendered with `|safe` in public templates.

Before treating external API text as trusted HTML, either:

- remove `|safe` and render the text escaped, or
- introduce explicit allowlist sanitization for permitted tags and attributes.

Review affected templates including:

- `templates/operations_portalcms_django/access_allocated.html`
- `templates/operations_portalcms_django/access_online_services.html`
- `templates/operations_portalcms_django/resource_detail.html`

## External Assets And Links

Review third-party frontend assets and external links:

- add `rel="noopener noreferrer"` to every `target="_blank"` link
- consider vendoring or integrity-pinning CDN assets
- review whether external JavaScript dependencies are acceptable for the deployment environment

## Authentication Review

Review the authentication and account-management posture before production hardening:

- CILogon auto-signup
- local Django password login policy
- email-based CILogon account linking
- `SOCIALACCOUNT_STORE_TOKENS`
- staff/superuser assignment process
- group sync from CILogon claims

## Test Isolation

The scripts in `tests/` are not isolated unit tests. They call `django.setup()` and mutate whichever database `APP_CONFIG` selects.

Future work should either:

- convert these scripts into isolated Django tests with disposable databases, or
- add a test workflow that refuses to run against RDS `portal1`.

## Dependency And Artifact Hygiene

Future hardening should add dependency/security scanning, such as `pip-audit` or an equivalent CI check for the `uv.lock` environment.

Historical media and backup artifacts should be moved out of Git when practical. Future dumps and uploaded media should live in backups or artifact storage, not normal source history.
