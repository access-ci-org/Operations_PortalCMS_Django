# How Django CMS handles media 

See Django CMS easy-read [media-files page](https://user-guide.django-cms.org/en/latest/how-to/media-files.html) on how it handles media.

1. Django Filer handles the media itself (which is installed in settings.py)
2. Media files are stored in the `media/` directory at the project root
3. The `MEDIA_URL` and `MEDIA_ROOT` settings in `settings.py` define the URL path and filesystem location for serving these files
4. Media backups are being run by a cron job configured by Ansible, resolving the target destination to: `s3://backup.operations.access-ci.org/portal.operations.access-ci.org/media.backup/${DB_DATABASE}/` - which matches the DB backup naming convention with its corresponding media.

Most media work will be images and potentially videos uploaded to the Django CMS via the standard CMS editor that also has some plugins to handle the media being uploaded. There are already image plugins in the `djangocms-picture` package as well as a video plugin found in the installed `djangocms-video`.

## Main akeawayfrom the most common media interacion in the content editor is found in item 3 from the 'Managing Media Files' link referenced above:

"
**Inserting Files into Content**: When editing content in Django CMS, content editors can easily insert files (images, documents) stored in django-filer using plugins or specific placeholders designed to handle media elements. For instance, they might use a “File” or “Image” plugin that allows them to select files from the django-filer library and place them within the content area.
"

## Retrieving and restoring media backups

Use the two scripts in `database/`. Requires the `opsbackupreader` AWS profile configured locally
(or `newbackup` on the production server).

### Step 1 — List available backups

```bash
# Production (portal1, default)
uv run database/media_retrieve.py -l

# Specific database
uv run database/media_retrieve.py -l media.portal_dev.
```

### Step 2 — Download the most recent backup

```bash
# Production (portal1, default) — downloads to database/mediarestore/
uv run database/media_retrieve.py -r

# Specific database
uv run database/media_retrieve.py -r media.portal_dev.
```

### Step 3 — Restore (dry run first, then full)

```bash
# Preview what will be extracted
bash database/media_restore.sh database/mediarestore/media.portal1.<epoch>.tar --dry-run

# Local dev (extracts to operations_portalcms_django/media/ by default)
bash database/media_restore.sh database/mediarestore/media.portal1.<epoch>.tar

# Production — Ansible-managed server
bash database/media_restore.sh database/mediarestore/media.portal1.<epoch>.tar \
  --target-dir /soft/django-cms-01/www/media

# Production — pre-Ansible / manual deploy
bash database/media_restore.sh database/mediarestore/media.portal1.<epoch>.tar \
  --target-dir /soft/django-cms-01/tags/{app_tag}/operations_portalcms_django/media
```

The restore script verifies that `filer_public/` and `filer_public_thumbnails/` are present
after extraction and prints file counts. No database connection or `APP_CONFIG` required.