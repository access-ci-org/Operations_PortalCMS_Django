# Database and Media Dumps

This directory contains backup dumps for deployment.

## Current Files (Initial Deployment)

- `portalcms_production_20260216_133655.sql.gz` - Database dump from local djangocmsjoy
  - Contains: All tables, CMS pages, users, news items
  - Database: djangocmsjoy → Will restore as: portalcms1
  - User: jelambeadmin → Will restore as: portalcms_django
  - Size: 50KB

- `media_backup_20260216_134007.tar.gz` - Media files archive
  - Contains: 32 uploaded images (18MB)
  - Includes: filer_public/ and filer_public_thumbnails/ directories

## Production Deployment Usage

On the remote server after `git pull`:

```bash
# 1. Restore database
cd /soft/django-cms-01/PROD/Operations_PortalCMS_Django
gunzip -c database/dumps/portalcms_production_20260216_133655.sql.gz | \
  psql -U portalcms_django -d portalcms1

# 2. Extract media files
tar -xzf database/dumps/media_backup_20260216_134007.tar.gz

# 3. Verify
ls -la media/filer_public/
psql -U portalcms_django -d portalcms1 -c "SELECT COUNT(*) FROM cms_page;"
```

## Important Notes

- These dumps are for **initial deployment only** with development data
- After production deployment, re-enable `.gitignore` rules for `database/dumps/`
- Future dumps should NOT be committed to git
- Use the backup scripts in `database/` directory for production backups

## Cleanup After First Deployment

After successful production deployment, you should:

1. Re-enable gitignore rules in `.gitignore`:
   ```bash
   # Uncomment these lines:
   database/dumps/*.dump
   database/dumps/*.sql
   database/dumps/*.gz
   ```

2. Remove these initial dump files from git:
   ```bash
   git rm --cached database/dumps/*.gz
   git commit -m "Remove initial deployment dumps from tracking"
   ```

3. Use production backup scripts for future backups (not committed to repo)
