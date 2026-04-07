# CMS Versioning Clone Checklist

Historical note:

- This checklist documents the clone-first validation path that was completed before promotion.
- On 2026-04-06, `portalcms1_clone` was promoted to the canonical `portalcms1` name and the former `portalcms1` was archived as `portalcms1_old`.
- The temporary clone-specific runtime files referenced below were retired after that cutover.

This is the hands-on checklist for rolling out django CMS page versioning safely in the clone database first.

Important:

- This project is **not** currently in a clean first-install state.
- The database already contains stranded old `djangocms_versioning_*` and `djangocms_moderation_*` tables.
- Use this checklist against `portalcms1_clone` first.
- Do not point these steps at `portalcms1` until the clone path is proven end-to-end.

## Scope

This checklist is for the focus-area page workflow:

1. page-specific editor saves draft changes
2. public site keeps showing the published version
3. `Focus_area_editors` reviews and publishes

## Current Known Inputs

- Clone config:
  `/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json`
- Deployed clone config used for server-side browser testing:
  `/soft/django-cms-01/conf/portal-clone.conf.json`
- Fresh backup:
  `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/portalcms1_post_migrate_20260401T185011Z.dump`
- Target clone database:
  `portalcms1_clone`
- Clone systemd unit:
  `/etc/systemd/system/portal-clone.service`
- Clone socket:
  `/soft/django-cms-01/run/portal-clone.socket`
- Clone nginx site:
  `/etc/nginx/sites-available/nginx.portal-clone`

## Verified Result

As of 2026-04-03, the clone-first versioning test has already been proven for the STEP page:

- `djangocms_versioning` installed and migrated in clone
- initial version bootstrap completed successfully
- page-specific editor created a new draft
- reviewer/superuser published the new version
- clone DB reflected the publish as a new `cms_pagecontent` row and new current version

Current verified clone DB state after that test:

- `cms_pagecontent = 19`
- `djangocms_versioning_version = 19`
- version states: `published:18, unpublished:1`

This means versioning-only workflow is working in the clone environment. Moderation is still deferred.

## Public Browser Test Path

For real browser testing on the server, a temporary clone-backed public path was created:

- public hostname: `https://cms2.operations.access-ci.org/`
- active public nginx vhost temporarily repointed from:
  - `/soft/django-cms-01/run/portal.socket`
  to:
  - `/soft/django-cms-01/run/portal-clone.socket`

Backup of the original public nginx vhost created during the switch:

- `/etc/nginx/sites-available/nginx.portalcms.bak_20260403T194558Z`

This repoint should be considered temporary and should be reverted when clone testing is complete.

## Phase 0: Preflight

Run these from the repo root:

```bash
pwd
git status --short
ls -1 backups
```

Confirm the app can resolve the clone config before doing anything else:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py check
```

Confirm Django resolves the clone DB, not live:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.conf import settings; print(settings.DATABASES['default']['NAME'])"
```

Expected result:

- `portalcms1_clone`

## Phase 1: Refresh The Clone

Preview the exact restore first:

```bash
./database/clone_db.sh \
  portalcms1_clone \
  backups/portalcms1_post_migrate_20260401T185011Z.dump \
  --dry-run
```

Restore the newest safe dump into the clone DB:

```bash
./database/clone_db.sh \
  portalcms1_clone \
  backups/portalcms1_post_migrate_20260401T185011Z.dump
```

Verify the clone DB directly:

```bash
DB_DATABASE=portalcms1_clone ./database/verify_db.sh
```

Verify the app still points to the clone DB after restore:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.conf import settings; from cms.models import Page; print({'db': settings.DATABASES['default']['NAME'], 'page_count': Page.objects.count()})"
```

Expected result:

- `db` is `portalcms1_clone`
- `page_count` is sane and non-zero

## Phase 2: Inventory Existing Versioning And Moderation State

List existing versioning/moderation tables in the clone:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select tablename from pg_tables where schemaname='public' and (tablename like 'djangocms_versioning_%' or tablename like 'djangocms_moderation_%') order by tablename\"); print([row[0] for row in cur.fetchall()])"
```

Count rows in the key versioning tables:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select count(*) from cms_pagecontent\"); pagecontent=cur.fetchone()[0]; cur.execute(\"select count(*) from djangocms_versioning_version\"); versions=cur.fetchone()[0]; cur.execute(\"select count(*) from djangocms_versioning_statetracking\"); tracking=cur.fetchone()[0]; print({'cms_pagecontent': pagecontent, 'djangocms_versioning_version': versions, 'djangocms_versioning_statetracking': tracking})"
```

Check migration history rows related to versioning/moderation:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select app, name from django_migrations where app in ('djangocms_versioning', 'djangocms_moderation') order by app, name\"); print(cur.fetchall())"
```

Find `cms_pagecontent` rows that do not currently have a version row:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select pc.id, pc.title, p.path from cms_pagecontent pc join cms_page p on p.id = pc.page_id left join djangocms_versioning_version v on v.object_id = pc.id where v.object_id is null order by p.path, pc.language, pc.id\"); print(cur.fetchall())"
```

At this point, write down what you found before cleaning anything up.

## Phase 3: Cleanup-First Reconciliation In Clone

This phase is intentionally destructive, but only in `portalcms1_clone`.

Run the cleanup script below only after you have confirmed:

- `APP_CONFIG` points to `portalcms1_clone`
- the clone has just been refreshed from the safe dump
- you are not connected to `portalcms1`

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python - <<'PY'
import os
import django

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "operations_portalcms_django.settings")
django.setup()

from django.conf import settings
from django.db import connection

assert settings.DATABASES["default"]["NAME"] == "portalcms1_clone", settings.DATABASES["default"]["NAME"]

statements = [
    "DROP TABLE IF EXISTS djangocms_moderation_collectioncomment CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_confirmationformsubmission CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_confirmationpage CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_moderationcollection CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_moderationrequest CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_moderationrequestaction CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_moderationrequesttreenode CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_requestcomment CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_role CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_workflow CASCADE",
    "DROP TABLE IF EXISTS djangocms_moderation_workflowstep CASCADE",
    "DROP TABLE IF EXISTS djangocms_versioning_statetracking CASCADE",
    "DROP TABLE IF EXISTS djangocms_versioning_version CASCADE",
    "DELETE FROM django_migrations WHERE app IN ('djangocms_versioning', 'djangocms_moderation')",
]

with connection.cursor() as cur:
    for statement in statements:
        cur.execute(statement)
        print(statement)

print("Clone-only cleanup complete.")
PY
```

Re-check that the old tables and migration rows are gone:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select tablename from pg_tables where schemaname='public' and (tablename like 'djangocms_versioning_%' or tablename like 'djangocms_moderation_%') order by tablename\"); print([row[0] for row in cur.fetchall()]); cur.execute(\"select app, name from django_migrations where app in ('djangocms_versioning', 'djangocms_moderation') order by app, name\"); print(cur.fetchall())"
```

## Phase 4: Add Packages In Code

The repo now includes `djangocms-versioning` in `pyproject.toml`.

Add versioning first:

```bash
uv add djangocms-versioning
```

If you are explicitly testing the moderation package in a later pass, add it too:

```bash
uv add djangocms-moderation
```

Then update `operations_portalcms_django/settings.py`.

Add these apps to `INSTALLED_APPS`:

```python
'djangocms_versioning',
```

Recommended initial settings:

```python
DJANGOCMS_VERSIONING_LOCK_VERSIONS = True
DJANGOCMS_VERSIONING_ON_PUBLISH_REDIRECT = "published"
```

Optional, but convenient for bootstrap:

```python
DJANGOCMS_VERSIONING_DEFAULT_USER = <migration-user-pk>
```

Note:

- If the first rollout is only proving true draft/publish for pages, `djangocms_versioning` is the critical package.
- The repo's current rollout plan still treats `djangocms_moderation` as an open decision for the first pass.

## Phase 5: Migrate In Clone

Check that Django now sees the package migrations:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py showmigrations | rg 'djangocms_(versioning|moderation)'
```

Run migrations against the clone DB only:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py migrate
```

Observed clone-specific note:

- `djangocms_versioning.0009_cms_pagecontent_remove_unique_constraint` had to be fake-applied in clone because this DB no longer had the old `cms_pagecontent(language, page_id)` uniqueness constraint that the migration expects to remove.
- Remaining versioning migrations then completed successfully.

Re-check the CMS counts after migration:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select count(*) from cms_page\"); page_count=cur.fetchone()[0]; cur.execute(\"select count(*) from cms_pagecontent\"); pagecontent_count=cur.fetchone()[0]; cur.execute(\"select count(*) from cms_placeholder\"); placeholder_count=cur.fetchone()[0]; cur.execute(\"select count(*) from cms_cmsplugin\"); plugin_count=cur.fetchone()[0]; print({'cms_page': page_count, 'cms_pagecontent': pagecontent_count, 'cms_placeholder': placeholder_count, 'cms_cmsplugin': plugin_count})"
```

If those counts drift unexpectedly, stop and rebuild the clone from the dump before continuing.

## Phase 6: Bootstrap Initial Published Versions

Official `djangocms-versioning` provides a `create_versions` management command for existing content.

First, create or identify the user that should own the initial bootstrap versions.

List superusers and staff users:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); print(list(User.objects.filter(is_staff=True).values_list('id','username','is_superuser')))"
```

If needed, create a dedicated migration user:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.contrib.auth import get_user_model; User=get_user_model(); u, created = User.objects.get_or_create(username='migration', defaults={'email':'migration@example.com','is_staff':True,'is_superuser':True}); print({'id': u.pk, 'created': created})"
```

Dry-run the bootstrap first. Replace `1` with the chosen user id if needed:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py create_versions --userid 4 --state published --dry-run
```

Run the bootstrap for real:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py create_versions --userid 4 --state published
```

Verify that every relevant `cms_pagecontent` row now has a version:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select count(*) from cms_pagecontent\"); pagecontent=cur.fetchone()[0]; cur.execute(\"select count(*) from djangocms_versioning_version\"); versions=cur.fetchone()[0]; cur.execute(\"select pc.id, pc.title from cms_pagecontent pc left join djangocms_versioning_version v on v.object_id = pc.id where v.object_id is null order by pc.id\"); missing=cur.fetchall(); print({'cms_pagecontent': pagecontent, 'versions': versions, 'missing': missing[:20]})"
```

Check the state distribution:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py shell -c "from django.db import connection; cur=connection.cursor(); cur.execute(\"select state, count(*) from djangocms_versioning_version group by state order by state\"); print(cur.fetchall())"
```

Expected result after cleanup-first bootstrap:

- one published version for each current page-content grouper
- no missing `cms_pagecontent` rows

Observed result after clone browser test and reviewer publish:

- one page (`STEP`) now has a newer published version and an older `unpublished` version
- total `cms_pagecontent` rows increased from 18 to 19
- total version rows increased from 18 to 19

## Phase 7: Validate Workflow In Clone

Re-run permission setup to make sure the page groups are still aligned:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py setup_groups
```

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python manage.py setup_focus_area_page_permissions
```

Run the existing focus-area workflow test:

```bash
APP_CONFIG=/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json \
uv run python tests/test_focus_area_page_workflow.py
```

Then do the browser workflow check in the clone-backed app:

1. log in as a page-specific editor
2. edit one focus-area page
3. save draft
4. confirm anonymous/public view still shows the previous published content
5. log in as a `Focus_area_editors` user
6. publish the reviewed version
7. confirm the public page now shows the change

## Phase 8: Production Go/No-Go

Do not touch `portalcms1` until all of these are true:

- clone DB is verified
- migrations ran cleanly in clone
- `create_versions --state published` completed cleanly
- public content stayed unchanged until publish
- reviewer publish succeeded in browser testing

Once all of that is true, copy this exact sequence into a production runbook and repeat it with:

- a fresh live backup first
- explicit live DB target verification first
- pre/post table counts captured
- a rollback path using the fresh dump

## Notes

- The current repo docs still correctly say this is a reconciliation rollout, not a clean install.
- The safest first pass is still `djangocms_versioning` on clone.
- If `djangocms_moderation` turns out to be unnecessary for the first page workflow, stop after proving versioning alone.
