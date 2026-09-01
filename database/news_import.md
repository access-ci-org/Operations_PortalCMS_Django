# Drupal News Cutover Import Runbook

This runbook covers the one-time replacement of both Drupal news feeds in Django:

- Drupal `infrastructure_news_v2` -> Django `SystemStatusNews`
- Drupal `integration_news_v1` -> Django `IntegrationNews`

The same command is rehearsed repeatedly with recent MySQL dumps on a nonproduction
host. The final run uses the frozen cutover dump. This is not a synchronization service.
After acceptance and the rollback window, the importer and this runbook can be removed in
a later reviewed release.

No migration, deployment, service restart, or database restore is performed by the import
command. Those remain separate human-approved actions.

## Runtime and operator contract

Run deployed rehearsals and cutover commands as the `software` operating-system user.
Ansible builds an immutable `.venv` inside every release from the host-selected, locked uv
profile. Invoke that interpreter directly; do not create a second environment for the
importer.

`/soft/django-cms-01/sbin/manage.prod.sh` is host-specific. On beta it selects beta's active
`PROD` release and stable beta config; on production it selects production's active release
and stable production config. It is acceptable only when the active release is exactly the
approved importer release. The explicit release commands below are preferred for the
change record because they pin the code and `.venv` visibly.

The identities involved are different:

| Purpose | Identity |
|---|---|
| OS process owner | `software` |
| Python runtime | `<approved-release>/.venv/bin/python` |
| PostgreSQL role | Loaded by Django from the host-specific `APP_CONFIG` |
| Django author for imported rows | Existing user supplied with `--import-user` |

Never print the configuration file or credentials. The importer reports only the database
name, write host, source path and checksum, Python executable, counts, warnings and errors.

## Import safety contract

Raw-dump imports enforce all of the following:

1. The source is an explicit plain SQL or `.gz` MySQL dump.
2. Both Drupal bundles must be present and nonempty.
3. Raw dumps can only use atomic `--replace`; additive raw-dump imports are refused.
4. `--confirm-database` and `--confirm-host` must match resolved Django settings.
5. `--dry-run` and `--apply` are mutually exclusive; replacement without either is refused.
6. A write requires the exact reviewed source SHA-256 and operator-confirmed feed counts.
7. A raw-dump write requires `--strict`, an existing import user, and
   `--suppress-notifications`.
8. Drupal node IDs and revisions, field-table revisions, types, dates, references and
   choice mappings are validated before PostgreSQL replacement begins.
9. Only Infrastructure News that is current or future at the operator-approved cutover
   timestamp is retained. Every affected infrastructure and integration-element reference
   on a retained record is preserved; unknown, missing or duplicate relationships fail
   validation or become strict-mode failures.
10. Delete, import, stable-ID assignment, relationship creation, full field/relationship
    verification and final stable-ID-set verification share one PostgreSQL transaction.
11. Any failure rolls back the complete replacement.
12. Replacement imports require a timezone-aware `--system-news-as-of` value. Dry-run
    and apply must use the identical value, and every cutoff-excluded Drupal nid is
    recorded in the report.
13. Requested explicit exclusions must exist exactly once. Named source corrections
    require an exact original-value match and fail rather than changing an unexpected
    value.
14. Every run writes a Markdown report, including the cutoff, cutoff exclusions, explicit
    exclusions and corrections. Parser failures are also recorded.

The parser reads only current Drupal field tables and ignores unrelated dump tables. It
uses no live MySQL or Drupal API connection.

## Approved cutover window and source correction

Infrastructure News is a cutover snapshot, not a historical archive. The importer keeps
the union of records that are current or future at `--system-news-as-of`:

- current: start is at or before the cutoff and end is absent or at or after the cutoff;
- future: start is at or after the cutoff.

Everything else is past and is excluded with its Drupal nid recorded in the report. The
cutoff must be an explicit timezone-aware ISO-8601 timestamp. Select it once for each
rehearsal or cutover and reuse the exact string for dry-run and apply. The importer never
uses its live clock or calls the Operations API to make this decision. Integration News
is not date-filtered.

One source correction remains necessary before the cutoff can be evaluated: correct only
nid `928`'s start datetime from the exact source value
  `0026-01-07T12:50:36` to `2026-01-07T12:50:36` by supplying
`--source-correction infrastructure-928-start-year`. Its Drupal creation timestamp and
end datetime are both in January 2026. If the original start value changes, the importer
refuses the correction. Whether this corrected record is retained then depends only on the
approved cutoff.

Do not reuse the previous full-history counts. Record the retained SystemStatusNews count,
infrastructure-relationship count and cutoff-excluded nid list from the successful strict
dry-run. For the reviewed August 31 dump, the unfiltered Integration News count remains 17
and its expected relationship count remains 39. Later dumps must be reviewed from their
own report.

Do not edit the dump. Its SHA-256 continues to identify the exact source artifact, while
the report records the exclusion and correction separately.

## Rehearsal on beta

### 1. Human prerequisites

Before running anything:

- Deploy or prepare the approved application release on the beta host through the normal
  infrastructure workflow.
- Obtain separate approval for modifying the beta PostgreSQL database.
- Place a recent MySQL dump in an operator-approved location outside Git.
- Create a durable, `software`-writable change-record directory for reports and checksums.
- Know the exact beta database name and write host.
- Confirm the selected Django import user already exists. Do not create it in the importer.
- Select and record the exact timezone-aware Infrastructure News cutoff timestamp.

Committing and pushing the branch does not update an existing release. Use a newly
deployed immutable release built from the exact commit containing the importer changes;
do not use the older `news_apis_imports_testing-...` release or the normalized JSON under
`/soft/django-cms-01/tags/`. The local `database/dumps/` directory is ignored by Git, so
copy the reviewed raw dump separately to a durable location readable by `software`.

### 2. Start a `software` login shell and pin the release

```bash
sudo -i -u software

APP_HOME=/soft/django-cms-01
RELEASE=/soft/django-cms-01/releases/<approved-release>
PYTHON="$RELEASE/.venv/bin/python"
MANAGE="$RELEASE/operations_portalcms_django/manage.py"
APP_CONFIG="$APP_HOME/conf/portal.conf"
SOURCE_DUMP=/path/to/backup_database-2026-08-31T04:00:03-05:00.mysql.gz
CHANGE_RECORD=/path/to/durable/change-record/rehearsal-N
IMPORT_USER=jlambertson
EXPECTED_DATABASE=portal_beta
EXPECTED_WRITE_HOST=<approved-beta-write-host>
SYSTEM_NEWS_AS_OF=REPLACE_WITH_APPROVED_UTC_CUTOVER_TIMESTAMP

export APP_CONFIG

test "$(id -un)" = software
test -x "$PYTHON"
test -r "$MANAGE"
test -r "$APP_CONFIG"
test -s "$SOURCE_DUMP"
test -d "$CHANGE_RECORD"
test -n "$EXPECTED_WRITE_HOST"
test "$SYSTEM_NEWS_AS_OF" != REPLACE_WITH_APPROVED_UTC_CUTOVER_TIMESTAMP
```

Do not continue if any check fails. Do not use a release path inferred from an old report.
Do not export `PYTHONPATH`; invoking the pinned release's `manage.py` with its own
`.venv/bin/python` selects the intended application code and environment.

### 3. Confirm the interpreter and target without exposing credentials

```bash
"$PYTHON" "$MANAGE" shell -c "
import sys
from django.conf import settings
database = settings.DATABASES['default']
print('python:', sys.executable)
print('database:', database.get('NAME'))
print('write host:', database.get('HOST'))
print('port:', database.get('PORT'))
"
```

Stop unless the Python path is under `$RELEASE/.venv` and the database and host exactly
match `EXPECTED_DATABASE` and `EXPECTED_WRITE_HOST`.

### 4. Record the source checksum

```bash
sha256sum "$SOURCE_DUMP" | tee "$CHANGE_RECORD/source.sha256"
```

Any source-file change invalidates every previous dry-run and report.

For the exact August 31 dump reviewed during importer development, the output is:

```text
ab48e0976af0eb18f075d19673400e357a19e1f876ca9e03162aa63e93d99b27
```

Stop if the server-side checksum differs. A later dump must use its own checksum.

### 5. Run the strict atomic replacement dry-run

```bash
"$PYTHON" "$MANAGE" import_drupal_news \
  --mysql-dump "$SOURCE_DUMP" \
  --replace \
  --dry-run \
  --strict \
  --confirm-database "$EXPECTED_DATABASE" \
  --confirm-host "$EXPECTED_WRITE_HOST" \
  --system-news-as-of "$SYSTEM_NEWS_AS_OF" \
  --source-correction infrastructure-928-start-year \
  --suppress-notifications \
  --report-file "$CHANGE_RECORD/import-dry-run.md" \
  --import-user "$IMPORT_USER"
```

Review the complete report. It must show:

- the pinned release Python executable;
- the intended database and write host;
- the same SHA-256 recorded in `source.sha256`;
- nonzero and expected record counts for both feeds;
- expected infrastructure and integration-element relationship counts;
- the exact `SYSTEM_NEWS_AS_OF` value;
- every past Infrastructure News nid excluded by that cutoff;
- no explicit nid exclusions unless separately reviewed;
- the exact-match nid `928` start-datetime correction and no other correction;
- zero errors and zero warnings under strict mode.

A dry-run performs ORM work inside a transaction and then forces rollback. Confirm that
the beta row counts are unchanged after the dry-run.

Record these values from the successful adjusted dry-run:

```text
Infrastructure News cutoff: <exact SYSTEM_NEWS_AS_OF value>
SystemStatusNews: <retained current/future count>
IntegrationNews: <unfiltered count; 17 for the reviewed August 31 dump>
Infrastructure relationships: <retained relationship count>
Integration-element relationships: <39 for the reviewed August 31 dump>
Cutoff-excluded past SystemStatusNews nids: <complete reported list>
Explicitly excluded SystemStatusNews nids: None
Corrected SystemStatusNews nid: 928
Warnings: 0
Errors: 0
```

### 6. Back up the beta target

Use the repository's targeted PostgreSQL backup procedure with the beta `APP_CONFIG` and
the same confirmed write host. Store the backup in the durable change-record location.
This is a separate production-data-style operation and requires its own human approval.
Do not continue unless the backup exists and is nonempty.

### 7. Apply the reviewed dump

Copy the 64-character checksum and the two source counts from the reviewed dry-run report.
Then run:

```bash
# Copy these values from the successful dry-run of the exact source and cutoff.
SOURCE_SHA256=ab48e0976af0eb18f075d19673400e357a19e1f876ca9e03162aa63e93d99b27
CONFIRM_SYSTEM_COUNT=REPLACE_WITH_DRY_RUN_SYSTEM_COUNT
CONFIRM_INTEGRATION_COUNT=17

test "$CONFIRM_SYSTEM_COUNT" != REPLACE_WITH_DRY_RUN_SYSTEM_COUNT
sha256sum --check "$CHANGE_RECORD/source.sha256"

"$PYTHON" "$MANAGE" import_drupal_news \
  --mysql-dump "$SOURCE_DUMP" \
  --replace \
  --apply \
  --strict \
  --confirm-database "$EXPECTED_DATABASE" \
  --confirm-host "$EXPECTED_WRITE_HOST" \
  --confirm-source-sha256 "$SOURCE_SHA256" \
  --confirm-system-count "$CONFIRM_SYSTEM_COUNT" \
  --confirm-integration-count "$CONFIRM_INTEGRATION_COUNT" \
  --system-news-as-of "$SYSTEM_NEWS_AS_OF" \
  --source-correction infrastructure-928-start-year \
  --suppress-notifications \
  --report-file "$CHANGE_RECORD/import-apply.md" \
  --import-user "$IMPORT_USER"
```

Before apply, verify `SYSTEM_NEWS_AS_OF` is byte-for-byte identical to the dry-run report.
For a later dump, replace the checksum and both counts with values from that dump's
successful dry-run report. Never reuse reviewed values for a different file or cutoff.

### 8. Verify the database and rendered application

```bash
"$PYTHON" "$MANAGE" shell -c "
from infrastructure_news.models import SystemStatusNews
from integration_news.models import IntegrationNews

print('system rows:', SystemStatusNews.objects.count())
print('system null outage_id:', SystemStatusNews.objects.filter(outage_id__isnull=True).count())
print('system relationships:', sum(item.affected_infrastructure_items.count() for item in SystemStatusNews.objects.all()))
print('integration rows:', IntegrationNews.objects.count())
print('integration null integration_news_id:', IntegrationNews.objects.filter(integration_news_id__isnull=True).count())
print('integration relationships:', sum(item.affected_elements.count() for item in IntegrationNews.objects.all()))
"
```

Compare all four counts with the apply report. Then manually verify representative oldest,
newest, multi-resource, multi-element, empty/optional-field and HTML-heavy records through
the beta pages and both JSON APIs. Confirm no migration email or Slack notification was
sent.

### 9. Repeat the rehearsal

Repeat dry-run, apply and verification at least once with the same approved release and
dump. Because replacement is deterministic, the second apply must produce the same row,
stable-ID and relationship counts. Preserve a separate report directory for each run.

Repeat again after any code change, source correction, new dump, dependency-lock change or
target configuration change. A different SHA-256 is a new rehearsal input.

## Final cutover

The final cutover uses the same command sequence and flags as the successful beta
rehearsals, with these controlled substitutions:

- Use the final frozen MySQL dump taken after Drupal becomes read-only.
- Pin the specifically approved production release and its `.venv`.
- Run as `software` on the production CMS host.
- Use the host-specific production `APP_CONFIG`.
- Set `EXPECTED_DATABASE` to the approved production database and
  `EXPECTED_WRITE_HOST` to its approved write endpoint.
- Use a durable production change-record directory.
- Take and verify a PostgreSQL backup from the same write host immediately before apply.
- Require the active maintenance window and separate final data-change authorization.

Do not reuse a beta checksum, report, count confirmation, config file or backup. Run a new
strict dry-run against the final frozen dump, review it, record its SHA-256 and counts, then
apply that exact file.

If the command fails, its PostgreSQL transaction rolls back. Do not retry until the error
is understood. If it commits but acceptance fails, keep Drupal read-only, stop additional
writes and obtain separate approval for the whole-database restore procedure. The importer
does not perform restoration.

## Post-cutover retirement

Do not remove tooling immediately after the command commits. Wait until:

1. Database, page and API acceptance is complete.
2. Drupal retirement and rollback decisions are closed.
3. The source dump, reports, checksums and pre-cutover backup have been retained in their
   approved durable locations.

A later reviewed cleanup release may remove:

- `infrastructure_news/drupal_mysql.py`;
- `infrastructure_news/management/commands/import_drupal_news.py`;
- the `portal` command compatibility shim;
- importer/parser tests and fixtures;
- this runbook and import-only documentation.

From the Git root, after every retirement condition above is satisfied, remove the
importer, parser, compatibility shim, their dedicated tests, and this runbook with:

```bash
rm -- \
  operations_portalcms_django/infrastructure_news/drupal_mysql.py \
  operations_portalcms_django/infrastructure_news/management/commands/import_drupal_news.py \
  operations_portalcms_django/infrastructure_news/test_drupal_mysql.py \
  operations_portalcms_django/infrastructure_news/test_import_drupal_news.py \
  operations_portalcms_django/portal/management/commands/import_drupal_news.py \
  dev_documentation/prod_dev_content_comparison.md \
  database/news_import.md
```

Review the resulting Git diff before committing the cleanup release. This command does
not remove `dev_documentation/integration_news_v1_work.md`, because that document also
records the separate Integration News API work; archive or edit it as part of the reviewed
cleanup if it is no longer useful.

Do not remove Django migration files, stable-ID fields, normalized relationship models,
runtime APIs, or generic database backup/restore tooling. Raw dumps, reports and backups
must never be committed to Git.
