# Drupal News Import Runbook

Targeted data-only import of both Drupal feeds into the current Django schema.

- Infrastructure News -> `portal_systemstatusnews`
- Integration News -> `portal_integrationnews`
- No model changes, migrations, deployments, or full database restores.

## Operator

Run as `software`:

```bash
sudo -i -u software
cd /soft/django-cms-01/releases/api-syncing-changes-e1163643f845-19d6e816f90f-1787087656
#OR
cd /soft/django-cms-01/PROD
```

The PostgreSQL role is `portal_django`. The fallback Django content author is `jlambertson`.

## 1. Create the beta config

Do not use `/soft/django-cms-01/conf/portal.conf`; it is the production config.

```bash
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT
export WORK

.venv/bin/python - "$WORK" <<'PY'
import json
import pathlib
import sys

source = pathlib.Path("/soft/django-cms-01/conf/portal.conf.dev.json")
target = pathlib.Path(sys.argv[1]) / "portal_beta.json"

config = json.loads(source.read_text())
config["DB_DATABASE"] = "portal_beta"
target.write_text(json.dumps(config))
target.chmod(0o600)

print(target)
PY

export APP_CONFIG="$WORK/portal_beta.json"
export INPUT="$WORK/drupal_news_normalized_for_django.json"

grep -o '"DB_DATABASE"[[:space:]]*:[[:space:]]*"[^"]*"' "$APP_CONFIG"
```

The output must show:

```text
DB_DATABASE: portal_beta
```

## 2. Generate staging data

```bash
TAG=/soft/django-cms-01/tags/Operations_PortalCMS_Django
BACKUP=/soft/django-cms-01/releases/api-syncing-changes-e1163643f845-19d6e816f90f-1787087656/database/backup_database-2026-08-18T22:00:03-05:00.mysql.gz
#OR
BACKUP=/soft/django-cms-01/PROD/database/backup_database-2026-08-18T22:00:03-05:00.mysql.gz

sed \
  -e "s|DUMP_PATH = ROOT / .*|DUMP_PATH = Path(\"$BACKUP\")|" \
  -e "s|OUTPUT_DIR = ROOT / \"generated\"|OUTPUT_DIR = Path(\"$WORK\")|" \
  "$TAG/database/drupal_backups/analyze_news_migration.py" \
  > "$WORK/analyze_news_migration.py"

.venv/bin/python "$WORK/analyze_news_migration.py"

sed \
  -e "s|OUTPUT_DIR = ROOT / \"generated\"|OUTPUT_DIR = Path(\"$WORK\")|" \
  "$TAG/database/drupal_backups/normalize_news_for_django.py" \
  > "$WORK/normalize_news_for_django.py"

.venv/bin/python "$WORK/normalize_news_for_django.py"
```

Validate the payload:

```bash
.venv/bin/python - "$INPUT" <<'PY'
import json
import sys

payload = json.load(open(sys.argv[1]))
system = payload["SystemStatusNews"]
integration = payload["IntegrationNews"]

print("SystemStatusNews:", len(system))
print("IntegrationNews:", len(integration))
print("Unique system IDs:", len({
    str(row["source_metadata"].get("drupal_nid"))
    for row in system
}))
print("Unique integration IDs:", len({
    str(row["source_metadata"].get("drupal_nid"))
    for row in integration
}))
PY
```

Expected for the August 18 backup:

```text
SystemStatusNews: 244
IntegrationNews: 17
```

## 3. Dry-run both feeds

```bash
.venv/bin/python operations_portalcms_django/manage.py \
  import_drupal_news \
  --input "$INPUT" \
  --dry-run \
  --report-file "$WORK/news_import_dry_run.md" \
  --import-user jlambertson

sed -n '/## Summary/,/## Errors/p' \
  "$WORK/news_import_dry_run.md"
```

Review all warnings before writing.

Known warnings include:

- CIDER infrastructure IDs absent from the local cache
- Ambiguous integration-element mappings
- Unmatched Drupal authors

Unresolved integration elements become blank/N/A unless:

```text
--disallow-na-affected-element
```

is supplied.

## 4. Back up the beta database

This is a targeted import. Do not use `pg_restore_portal.sh`.

```bash
APP_CONFIG="$APP_CONFIG" ./database/pg_dump_portal.sh \
  --source-db portal_beta \
  --format sql \
  --output "$WORK/portal_beta_before_news_import.sql"

ls -lh "$WORK/portal_beta_before_news_import.sql"
```

Do not continue if the backup is missing or empty.

## 5. Import both feeds

```bash
.venv/bin/python operations_portalcms_django/manage.py \
  import_drupal_news \
  --input "$INPUT" \
  --report-file "$WORK/news_import_run.md" \
  --import-user jlambertson
```

Expected source counts:

```text
SystemStatusNews: 244
IntegrationNews: 17
Errors: 0
```

## 6. Verify stable IDs

Drupal `nid` is the stable external identifier.

The importer assigns stable IDs directly from `source_metadata.drupal_nid`. Do not run a
separate SQL backfill; replacement, ID assignment, relationship creation, and final ID
validation belong to the same importer transaction.

Verify the database:

```bash
.venv/bin/python operations_portalcms_django/manage.py shell -c "
from django.conf import settings
from infrastructure_news.models import SystemStatusNews
from integration_news.models import IntegrationNews

print('database:', settings.DATABASES['default']['NAME'])
print('system rows:', SystemStatusNews.objects.count())
print(
    'system null outage_id:',
    SystemStatusNews.objects.filter(outage_id__isnull=True).count()
)
print('integration rows:', IntegrationNews.objects.count())
print(
    'integration null integration_news_id:',
    IntegrationNews.objects.filter(
        integration_news_id__isnull=True
    ).count()
)
print(
    'system IDs 951-956:',
    list(
        SystemStatusNews.objects.filter(
            outage_id__in=[951, 952, 953, 954, 955, 956]
        ).values_list('outage_id', 'subject')
    )
)
"
```

Local draft/test records may legitimately remain without IDs.

## 7. Optional author mapping

Map original Drupal authors only when:

1. Drupal author email matches a Django `auth_user.email`
2. The match is case-insensitive
3. Exactly one Django user matches

Never create users automatically. Unmatched or retired Drupal authors remain assigned to `jlambertson`.

The current API does not expose author or updater fields.

## 8. Verify the public infrastructure API

```bash
curl -fsSL \
  "https://beta-operations.access-ci.org/api/infrastructure_news?verify=$(date +%s)" \
  -o "$WORK/infrastructure_api.json"

.venv/bin/python - "$WORK/infrastructure_api.json" <<'PY'
import json
import sys

rows = json.load(open(sys.argv[1]))

print("API rows:", len(rows))
print(
    "null outage_id:",
    sum(row.get("outage_id") is None for row in rows)
)
print(
    "951-956:",
    sorted(
        int(row["outage_id"])
        for row in rows
        if str(row.get("outage_id")) in {
            "951", "952", "953",
            "954", "955", "956"
        }
    )
)
PY
```

Expected:

```text
null outage_id: 0
951-956: [951, 952, 953, 954, 955, 956]
```

Integration News is a Django HTML page at:

```text
https://beta-operations.access-ci.org/integration-news/
```

It is not currently a public JSON API. Verify its database rows and page manually.

## Final `portal1` cutover

This is a one-time total replacement from the final Drupal MySQL dump. Drupal must be
read-only before that dump is taken and remain available, but read-only, until Django CMS
acceptance is complete. The complete Infrastructure News and Integration News history is
imported; closed and expired records are not filtered.

The replacement removes all current Django rows in both feeds, including local drafts and
test rows. It does not remove Django users, CMS pages or plugins, CIDER data, or unrelated
application data.

### When to run

Run only after all of the following are true:

1. The Drupal content freeze is active and the final MySQL dump is available.
2. The approved application release containing the atomic importer is installed.
3. The normalized payload passed review and its SHA-256 is recorded.
4. The `portal1` maintenance window and final cutover approval are active.
5. An operator-approved durable directory exists for reports and the PostgreSQL backup.

### 1. Start the approved release as `software`

Run on the Django CMS target host:

```bash
sudo -i -u software
cd /soft/django-cms-01/releases/<approved-release>

export APP_CONFIG=/soft/django-cms-01/conf/portal.conf
export INPUT=/path/to/approved/drupal_news_normalized_for_django.json
export CHANGE_RECORD=/path/to/operator-approved/durable/change-record-directory
export EXPECTED_WRITE_HOST=<approved-portal1-write-host>

test -r "$APP_CONFIG"
test -s "$INPUT"
test -d "$CHANGE_RECORD"
test -n "$EXPECTED_WRITE_HOST"
sha256sum "$INPUT" | tee "$CHANGE_RECORD/input.sha256"
```

Do not edit `portal.conf`, and do not place the backup or reports under `$WORK` or another
directory removed by a shell exit trap.

### 2. Confirm the configured target without printing credentials

```bash
.venv/bin/python operations_portalcms_django/manage.py shell -c "
from django.conf import settings

database = settings.DATABASES['default']
print('database:', database['NAME'])
print('write host:', database['HOST'])
print('port:', database['PORT'])
"
```

Stop unless the database is `portal1` and the write host exactly matches the approved
value in `EXPECTED_WRITE_HOST`.

### 3. Run and review the atomic replacement dry-run

```bash
.venv/bin/python operations_portalcms_django/manage.py \
  import_drupal_news \
  --input "$INPUT" \
  --replace \
  --dry-run \
  --confirm-database portal1 \
  --confirm-host "$EXPECTED_WRITE_HOST" \
  --suppress-notifications \
  --report-file "$CHANGE_RECORD/news_import_dry_run.md" \
  --import-user jlambertson

sed -n '/## Summary/,/## Errors/p' \
  "$CHANGE_RECORD/news_import_dry_run.md"
```

The dry-run must complete successfully. Confirm that both staged feeds are nonempty, the
planned deletion and creation counts are expected, errors are zero, and every warning is
reviewed. Any change to the MySQL dump or normalized JSON invalidates this dry-run.

### 4. Back up `portal1` from the write host

`pg_dump_portal.sh` normally reads `DB_HOSTNAME_READ`. Override that selection for this
cutover so the backup comes from the same write target that the importer will modify:

```bash
APP_CONFIG="$APP_CONFIG" \
DB_HOSTNAME_READ="$EXPECTED_WRITE_HOST" \
./database/pg_dump_portal.sh \
  --source-db portal1 \
  --format sql \
  --output "$CHANGE_RECORD/portal1_before_news_cutover.sql"

test -s "$CHANGE_RECORD/portal1_before_news_cutover.sql"
```

Do not continue if the dump fails or the durable backup is empty.

### 5. Apply the atomic replacement

Reconfirm the recorded input SHA-256 immediately before applying. Then run:

```bash
sha256sum --check "$CHANGE_RECORD/input.sha256"

.venv/bin/python operations_portalcms_django/manage.py \
  import_drupal_news \
  --input "$INPUT" \
  --replace \
  --apply \
  --confirm-database portal1 \
  --confirm-host "$EXPECTED_WRITE_HOST" \
  --suppress-notifications \
  --report-file "$CHANGE_RECORD/news_import_run.md" \
  --import-user jlambertson
```

The command verifies nonempty feeds and unique positive Drupal IDs before deleting
anything. Deletion, import, stable-ID assignment, relationship creation, and final stable-ID
set validation share one PostgreSQL transaction. An error in any of those operations rolls
back the entire replacement. `--apply` is required for a replacement write.

### 6. Verify before promotion

Run the database verification from step 6, then verify both news pages and the
Infrastructure News API through the pre-promotion Django CMS endpoint. Confirm source and
database counts, stable IDs, authorship, mappings, rendered content, and that no migration
email or Slack notification was sent. Preserve all output in `$CHANGE_RECORD`.

### Rollback

- If the replacement command fails, its transaction rolls back automatically. Confirm the
  pre-cutover rows remain and do not rerun until the error is understood.
- If the command commits but a post-import acceptance check fails, do not promote Django
  CMS and keep Drupal read-only. Stop further writes to `portal1` and obtain separate human
  approval for a database restore using
  `$CHANGE_RECORD/portal1_before_news_cutover.sql` and the repository database-restore
  procedure. A restore is a whole-database operational action and is not part of this
  importer command.
- After a restore, repeat database and page verification before deciding whether to retry
  the cutover.

Never use the beta config for this cutover. Never run the replacement without the dry-run,
durable backup, target confirmations, active maintenance window, and explicit approval.
