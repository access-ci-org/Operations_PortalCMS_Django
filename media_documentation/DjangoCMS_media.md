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

## Getting media backups from S3
(Assumes you already have the proper us-east-2 credentials on your machine or can copy them to a remote server if needing to restore)

- To list all the dumps:

`aws s3 ls s3://backup.operations.access-ci.org/portal.operations.access-ci.org/media.backup/`

Then:
`aws s3 cp s3://backup.operations.access-ci.org/portal.operations.access-ci.org/media.backup/`

-- An Exammple of copying the most recent media dump to your device:

`aws s3 cp s3://backup.operations.access-ci.org/portal.operations.access-ci.org/media.backup/ media.portal_dev.2026-07-17T003001Z.tar ./media.portal_dev.2026-07-17T003001Z.tar`

The database name will likely be portal1 in most cases since that is the production naming location that connects them, but this is an example. 

Copy the `filer_public`  and `filer_public_thumbnails` to:

`{app_home}/{app_tag}/operations_portalcms_django/media/`

OR 

`Operations_PortalCMS_Django/operations_portalcms_django/media/` if working locally on your machine.