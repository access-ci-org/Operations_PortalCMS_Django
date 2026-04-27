# APP_CONFIG Contract

Date: 2026-04-24

This document records the current intended config contract for Operations Portal CMS while deployment is still partly manual and before infra automation becomes authoritative.

## Canonical Runtime Contract

1. `APP_CONFIG` is the single supported runtime config entry point for Django settings.
2. The live runtime currently uses `/soft/django-cms-01/conf/portal.conf.dev.json`.
3. The app expects the file referenced by `APP_CONFIG` to contain JSON.
4. Django startup stops immediately if `APP_CONFIG` is missing or cannot be loaded.
5. The current deployed config points at Amazon RDS database `portal1` with `DB_SSLMODE=require`.

## Canonical Repo Sample

1. The canonical tracked local developer sample config is `portal.local.example.json` at the repo root.
2. Developers should copy that sample to a private path such as `$HOME/.config/operations-portal-cms/portal.local.json` and point `APP_CONFIG` at the private copy.
3. Repo-root runtime config names such as `portal.conf.dev.json`, `portal.conf.json`, `portalcms.conf.dev.json`, and `portalcms.conf.json` should be treated as legacy/private compatibility names, not files to commit with real secrets.
4. New docs and helper scripts should prefer `APP_CONFIG` explicitly, not implicit filename discovery.

## Required Keys

The current required keys enforced in `operations_portalcms_django/settings.py` are:

- `DJANGO_SECRET_KEY`

Other keys may still be operationally important depending on environment and enabled integrations, but `DJANGO_SECRET_KEY` is the only key currently hard-required during startup.

Operationally important current keys include `APP_ENV`, `PUBLIC_HOSTNAME`, `ENVIRONMENT_BANNER_ENABLED`, `ENVIRONMENT_LABEL`, `DB_DATABASE`, `DB_HOSTNAME_READ`, `DB_HOSTNAME_WRITE`, `DB_PORT`, `DJANGO_USER`, `DJANGO_PASS`, `DB_SEARCH_PATH`, `DB_SSLMODE`, `STATIC_ROOT`, CILogon client settings, and app log paths.

Environment identity keys are optional and backward-compatible:

- `APP_ENV` identifies the role of the config, such as `local`, `development`, `staging`, or `production`.
- `PUBLIC_HOSTNAME` records the expected public host, such as `cms2.operations.access-ci.org`.
- `ENVIRONMENT_BANNER_ENABLED` controls whether a visible environment marker is shown.
- `ENVIRONMENT_LABEL` controls the marker text.

The older `DEVELOPMENT_SERVER_BANNER` and `DEVELOPMENT_SERVER_LABEL` keys remain supported as aliases for existing configs and templates. Production-like deployments should set environment identity and banner values explicitly instead of relying on filename/default behavior.

## Deployment Hardening Reference

Future security and production/staging hardening work is tracked in [SECURITY_HARDENING.md](./SECURITY_HARDENING.md).

This config contract only records the runtime config shape. Any new proxy, HTTPS, cookie, CSRF, or clickjacking settings should still be APP_CONFIG-driven so local development can keep those values disabled while staging/production enables them deliberately.

## Manual Commands

To match the live service behavior as closely as possible:

1. Use `manage.prod.sh` as the manual wrapper once rendered.
2. Keep that wrapper aligned with the installed `portal.service`.
3. Use the same `APP_CONFIG` path as the running service unless intentionally targeting a clone or alternate environment.

## Helper Script Guidance

1. Database and admin helper scripts should prefer `APP_CONFIG` first.
2. Repo-root config filename fallback should remain a local convenience only.
3. Legacy repo-root config names should not be treated as the primary contract going forward.

## Transition Direction

The future infra-managed model should preserve the same high-level contract:

1. Infra renders the deployed config file.
2. Systemd points at that file through `APP_CONFIG`.
3. Manual admin commands use the same config path and code path as the live service.

## Current State Reference

For the latest verified values and row counts, see [CURRENT_STATE.md](./CURRENT_STATE.md).
