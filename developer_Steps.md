# Developer Setup Steps

This is the local setup path for a developer running the Operations Portal CMS with `uv`, local PostgreSQL, and a recent backup of the `portal1` database.

Use only local development secrets and passphrases. The database backup, database password, Django secret key, and any optional OAuth credentials should be obtained through approved project channels and kept out of Git.

## Goal

By the end of this setup, you should have:

- Python dependencies installed through `uv`
- a local PostgreSQL database restored from a recent `portal1` backup
- a private local `APP_CONFIG` file
- Django checks passing
- the app running at `http://127.0.0.1:8000/`

## Do Not Use Shared RDS For Local Work

Do not point local development at the shared RDS `portal1` database.

Use a local PostgreSQL restore of a recent `portal1` backup instead.

Before running database-writing commands, confirm your config points at local PostgreSQL:

```bash
echo "$APP_CONFIG"
python -m json.tool "$APP_CONFIG" | sed -n '1,80p'
```

Stop if `DB_HOSTNAME_READ`, `DB_HOSTNAME_WRITE`, or `DB_DATABASE` points at the shared RDS host or `portal1`.

## What You Need

- Python 3.12
- `uv`
- PostgreSQL running locally
- a recent `portal1` database dump
- local PostgreSQL credentials for your own development database
- a local `DJANGO_SECRET_KEY`
- a copy of current uploaded media, if images/files matter for your work
- optional local CILogon client ID/secret, only if you are testing OAuth login locally

Generate a local Django secret key with:

```bash
uv run python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

## 1. Get The Code

```bash
git clone <repo-url>
cd Operations_PortalCMS_Django
```

## 2. Install Python Dependencies

```bash
uv sync
```

`pyproject.toml` and `.venv/` live at the repo root. Run `uv sync` from the repo root, not from inside `operations_portalcms_django/`.

## 3. Create A Local Database

Use local names so there is no confusion with production.

```bash
createuser portal_django --pwprompt
createdb portal1_local --owner portal_django
```

Create the application schema:

```bash
psql -d portal1_local
```

Inside `psql`:

```sql
CREATE SCHEMA IF NOT EXISTS portal_django AUTHORIZATION portal_django;
ALTER ROLE portal_django SET search_path TO portal_django, public;
\q
```

## 4. Restore The Database Backup

For a custom-format `.dump` file:

```bash
PGPASSWORD='<your-local-db-password>' \
pg_restore \
  -h localhost \
  -U portal_django \
  -d portal1_local \
  --no-owner \
  --no-acl \
  /path/to/portal1_backup.dump
```

For a plain `.sql` file:

```bash
PGPASSWORD='<your-local-db-password>' \
psql \
  -h localhost \
  -U portal_django \
  -d portal1_local \
  -f /path/to/portal1_backup.sql
```

## 5. Create Your Local App Config

Create a private config file outside the repo:

```bash
mkdir -p "$HOME/.config/operations-portal-cms"
cp portal.local.example.json "$HOME/.config/operations-portal-cms/portal.local.json"
nano "$HOME/.config/operations-portal-cms/portal.local.json"
```

Use the example JSON as a starting point and replace the placeholder values:

```json
{
  "APP_ENV": "local",
  "PUBLIC_HOSTNAME": "localhost",
  "DEBUG": true,
  "ENVIRONMENT_BANNER_ENABLED": true,
  "ENVIRONMENT_LABEL": "LOCAL DEVELOPMENT",
  "ALLOWED_HOSTS": ["localhost", "127.0.0.1"],
  "DB_DATABASE": "portal1_local",
  "DB_PORT": "5432",
  "DB_HOSTNAME_READ": "localhost",
  "DB_HOSTNAME_WRITE": "localhost",
  "DJANGO_USER": "portal_django",
  "DB_OWNER": "portal_django",
  "DB_SEARCH_PATH": "portal_django,public",
  "DB_SSLMODE": "",
  "DJANGO_PASS": "<your-local-db-password>",
  "DJANGO_SECRET_KEY": "<your-local-django-secret-key>",
  "STATIC_ROOT": "./staticfiles",
  "APP_LOG": "./var/portal.log",
  "APP_ERROR_LOG": "./var/portal.error.log",
  "APP_VERSION": "local-dev",
  "SYSLOG_SOCK": "",
  "API_BASE": "",
  "CILOGON_CLIENT_ID": "",
  "CILOGON_CLIENT_SECRET": ""
}
```

Use this config for all local commands:

```bash
export APP_CONFIG="$HOME/.config/operations-portal-cms/portal.local.json"
```

Keep this file private. Do not commit it.

## APP_CONFIG Is Required For Local Commands

Run every Django or database helper command from a shell where `APP_CONFIG` is set:

```bash
export APP_CONFIG="$HOME/.config/operations-portal-cms/portal.local.json"
```

Or prefix one-off commands:

```bash
APP_CONFIG="$HOME/.config/operations-portal-cms/portal.local.json" uv run python operations_portalcms_django/manage.py check
APP_CONFIG="$HOME/.config/operations-portal-cms/portal.local.json" ./database/verify_db.sh
```

Do not rely on repo-root config discovery or a leftover private `portal.conf.dev.json`. If `APP_CONFIG` is unset, stop and set it explicitly.

## Project Directory

All Django commands (`manage.py`) run from inside the `operations_portalcms_django/` subdirectory, not the repo root:

```bash
cd operations_portalcms_django/
```

Set `APP_CONFIG` first (it uses an absolute path so it works from any directory), then run commands from inside `operations_portalcms_django/`. Keep `uv sync` at the repo root.

## 6. Check The Local App

```bash
cd operations_portalcms_django/
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py migrate --check
uv run python manage.py migrate --plan
```

For a current backup, `migrate --plan` should usually show no planned operations.

If `migrate --check` reports unapplied migrations, inspect `migrate --plan` before applying them. Only run migrations after confirming your `APP_CONFIG` points at your local database.

```bash
uv run python manage.py migrate
```

Optional database verification (run from repo root):

```bash
./database/verify_db.sh
```

## 7. Create A Local Admin User If Needed

If you do not have a usable admin account from the restored backup:

```bash
cd operations_portalcms_django/
uv run python manage.py createsuperuser
```

## 8. Run The Development Server

```bash
cd operations_portalcms_django/
uv run python manage.py runserver 127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/
```

Admin:

```text
http://127.0.0.1:8000/admin/
```

## 9. Media Files

The database restore does not include uploaded media files.

If pages show missing images/files, copy the current `media/` directory into `operations_portalcms_django/media/`:

```text
Operations_PortalCMS_Django/operations_portalcms_django/media/
```

## 10. Tests Warning

The scripts in `operations_portalcms_django/tests/` are not isolated unit tests. They modify whichever database `APP_CONFIG` points to.

Only run them against your local restored database:

```bash
cd operations_portalcms_django/
uv run python tests/test_news_permissions.py
uv run python tests/test_focus_area_page_workflow.py
```

## Local Notes

- A recent `portal1` backup should already contain CMS pages, news records, users, groups, permissions, CIDER cache rows, and migration history.
- Do not run setup or sync management commands unless your task explicitly requires it and you have confirmed the active database is local.
- Local runserver does not need production reverse-proxy or HTTPS settings.
- Future deployment and security hardening notes live in `dev_documentation/SECURITY_HARDENING.md`.

## Handoff Checklist

Before reporting your local setup as ready, record:

- local `APP_CONFIG` path
- local database name and host
- source/date of the restored `portal1` dump
- whether media files were copied locally
- output summary from `uv run python manage.py check`
- output summary from `uv run python manage.py migrate --plan`
- whether any mutating test scripts were run, and against which database

## Quick Daily Commands

```bash
export APP_CONFIG="$HOME/.config/operations-portal-cms/portal.local.json"
uv run python manage.py check
uv run python manage.py migrate --plan
uv run python manage.py runserver 127.0.0.1:8000
```
