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
| Django author for imported rows | Exact case-sensitive match of the derived Drupal username candidate, otherwise the existing user supplied with `--import-user` |

Never print the configuration file or credentials. The importer reports the database
name, write host, source path and checksum, Python executable, counts, usernames,
post timestamps, resolution reasons, warnings and errors. It does not report email or
password data.

## Import safety contract

Raw-dump imports enforce all of the following:

1. A dry-run uses an explicit dump or selects the newest valid timestamped dump from an
   explicit directory. Apply never rescans that directory.
2. Both Drupal bundles must be present and nonempty.
3. Raw dumps can only use atomic `--replace`; additive raw-dump imports are refused.
4. `--confirm-database` and `--confirm-host` must match resolved Django settings.
5. `--dry-run` and `--apply` are mutually exclusive; replacement without either is refused.
6. A strict dry-run writes a versioned JSON plan binding the source path and SHA-256,
   release interpreter, target, options, adjustments, IDs, counts, relationships,
   per-record author/post-date attribution and planned database outcome.
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
12. Replacement dry-runs require a timezone-aware `--system-news-as-of` value. Apply
    loads the exact value from the reviewed plan, and every cutoff-excluded Drupal nid is
    recorded in both artifacts.
13. Requested explicit exclusions must exist exactly once. Named source corrections
    require an exact original-value match and fail rather than changing an unexpected
    value.
14. Apply requires the reviewed plan file and its independently recorded SHA-256. It
    refuses a changed plan, source, release interpreter, target, correction definition,
    staged dataset or database outcome and rolls back transactional drift.
15. Each retained record preserves its original Drupal post timestamp in Django's
    displayed `created_at` field (and in `published_at` when published). For both feeds,
    a Drupal login containing one `@` is reduced to the local part before an exact,
    case-sensitive Django username match; a plain login is unchanged. Blank, deleted,
    malformed or unmatched names use the explicit `--import-user` fallback. Drupal uid,
    derived username candidate and method, selected Django username, resolution reason and
    post timestamp are bound per nid in the plan. Raw email-shaped logins, their domains,
    Drupal mail columns and password data are never retained or emitted.
16. Every run writes a Markdown report, including the plan identity, cutoff, cutoff
    exclusions, explicit exclusions, corrections and every author/post-date decision.
    Parser failures are also recorded.

The parser reads only the current Drupal node/field tables plus `uid` and `name` from the
Drupal users table, and ignores unrelated dump tables and user columns. It uses no live
MySQL or Drupal API connection.

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

Two reviewed source exclusions are required for the August 31 and September 1 source
family:

- nid `404` has empty content. The raw parser validates content before applying the date
  cutoff, so strict mode requires its explicit exclusion even though it is past;
- nid `797` is the historical Hive Gateway retirement. Its absent end date makes it look
  current to the generic cutoff rule, but its resource is no longer in active CIDER.

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

### 2. Start a `software` login shell and set one rehearsal contract

```bash
sudo -i -u software

APP_HOME=/soft/django-cms-01
RELEASE=/soft/django-cms-01/releases/<approved-release>
PYTHON="$RELEASE/.venv/bin/python"
MANAGE="$RELEASE/operations_portalcms_django/manage.py"
APP_CONFIG="$APP_HOME/conf/portal.conf"
SOURCE_DIRECTORY="$APP_HOME/var/news-import"
CHANGE_RECORD="$APP_HOME/var/news-import/beta-rehearsal-<unique-run-id>"
IMPORT_PLAN="$CHANGE_RECORD/import-plan.json"
IMPORT_USER=jlambertson
EXPECTED_DATABASE=portal_beta
EXPECTED_WRITE_HOST=<approved-beta-write-host>

# For a new beta rehearsal, capture now exactly once. For a deterministic replay,
# assign the exact cutoff from the earlier plan instead.
SYSTEM_NEWS_AS_OF="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
readonly SYSTEM_NEWS_AS_OF

export APP_CONFIG

test "$(id -un)" = software
test -x "$PYTHON"
test -r "$MANAGE"
test -r "$APP_CONFIG"
test -d "$SOURCE_DIRECTORY"
test -r "$SOURCE_DIRECTORY"
test -x "$SOURCE_DIRECTORY"
test -d "$CHANGE_RECORD"
test -w "$CHANGE_RECORD"
test ! -e "$IMPORT_PLAN"
test -n "$EXPECTED_WRITE_HOST"
printf 'Infrastructure News cutoff: %s\n' "$SYSTEM_NEWS_AS_OF"
```

Do not continue if any check fails. Do not use a release path inferred from an old report.
Do not export `PYTHONPATH`; invoking the pinned release's `manage.py` with its own
`.venv/bin/python` selects the intended application code and environment.

The directory selector considers only readable regular files whose names exactly match
`backup_database-<timezone-aware ISO timestamp>.mysql.gz`. It parses and compares those
timestamps rather than file modification times. A malformed candidate, unreadable file,
tie, or empty candidate set fails the dry-run. File ownership is not authoritative;
`test -r` as `software` and the importer checks are authoritative.

### 3. Confirm the release and target without exposing credentials

```bash
"$PYTHON" "$MANAGE" import_drupal_news --help | grep -F -- '--plan-file'
"$PYTHON" "$MANAGE" import_drupal_news --help | grep -F -- '--mysql-dump-directory'

"$PYTHON" "$MANAGE" shell --no-imports <<'PY'
import sys
from django.conf import settings
database = settings.DATABASES['default']
print('python:', sys.executable)
print('database:', database.get('NAME'))
print('write host:', database.get('HOST'))
print('port:', database.get('PORT'))
PY
```

Stop unless the Python path is under `$RELEASE/.venv` and the database and host exactly
match `EXPECTED_DATABASE` and `EXPECTED_WRITE_HOST`.

### 4. Run the strict atomic replacement dry-run and write the plan

```bash
(
  set -Eeuo pipefail

  "$PYTHON" "$MANAGE" import_drupal_news \
    --mysql-dump-directory "$SOURCE_DIRECTORY" \
    --replace \
    --dry-run \
    --strict \
    --confirm-database "$EXPECTED_DATABASE" \
    --confirm-host "$EXPECTED_WRITE_HOST" \
    --system-news-as-of "$SYSTEM_NEWS_AS_OF" \
    --exclude-system-nid 404 \
    --exclude-system-nid 797 \
    --source-correction infrastructure-928-start-year \
    --suppress-notifications \
    --plan-file "$IMPORT_PLAN" \
    --report-file "$CHANGE_RECORD/import-dry-run.md" \
    --import-user "$IMPORT_USER"
)
```

Review both complete artifacts. The JSON plan is machine-readable; the Markdown report is
the human-readable rendering of the run:

```bash
"$PYTHON" -m json.tool "$IMPORT_PLAN" | less
less "$CHANGE_RECORD/import-dry-run.md"
```

They must show:

- the pinned release Python executable;
- the exact selected absolute source path and SHA-256;
- the intended database and write host;
- the plan contract and schema versions;
- expected record counts, allowing zero retained Infrastructure News;
- expected infrastructure and integration-element relationship counts;
- every retained nid's original post timestamp, non-email username candidate, derivation
  method and selected Django author;
- every username fallback, with only `jlambertson` accepted for this cutover;
- the exact `SYSTEM_NEWS_AS_OF` value;
- every past Infrastructure News nid excluded by that cutoff;
- exactly the reviewed explicit exclusions `404` and `797` for this source family;
- the exact-match nid `928` start-datetime correction and no other correction;
- zero errors and zero warnings under strict mode.

Author fallbacks are review items rather than strict-mode warnings. Continue only when
every fallback is expected (for example, a deleted Drupal account) and resolves to the
approved `IMPORT_USER`. If a Django account is added or renamed after dry-run, apply
detects the changed resolution and refuses the plan.

A dry-run performs ORM work inside a transaction and then forces rollback. Confirm that
the beta row counts are unchanged after the dry-run.

For the September 1 beta rehearsal at cutoff `2026-09-01T18:43:13Z`, the reviewed values
were:

```text
Infrastructure News cutoff: <exact SYSTEM_NEWS_AS_OF value>
SystemStatusNews: 2
IntegrationNews: 17
Infrastructure relationships: 3
Integration-element relationships: 39
Cutoff-excluded past SystemStatusNews nids: <complete reported list>
Explicitly excluded SystemStatusNews nids: 404, 797
Corrected SystemStatusNews nid: 928
Warnings: 0
Errors: 0
```

These values are evidence for that exact source and cutoff, not reusable command inputs.
Apply obtains them from the plan.

### 5. Back up the beta target

Use the repository's targeted PostgreSQL backup procedure with the beta `APP_CONFIG` and
the same confirmed write host. Store the backup in the durable change-record location.
This is a separate production-data-style operation and requires its own human approval.
Do not continue unless the backup exists and is nonempty.

### 6. Apply only the exact reviewed plan

After human review, record the exact plan-file SHA-256. This is the only confirmation value
copied into apply:

```bash
PLAN_SHA256="$(sha256sum "$IMPORT_PLAN" | awk '{print $1}')"
readonly PLAN_SHA256
printf 'Reviewed import plan SHA-256: %s\n' "$PLAN_SHA256"

(
  set -Eeuo pipefail

  test -s "$IMPORT_PLAN"
  test -s /path/to/separately-approved-target-backup

  "$PYTHON" "$MANAGE" import_drupal_news \
    --apply \
    --plan-file "$IMPORT_PLAN" \
    --confirm-plan-sha256 "$PLAN_SHA256" \
    --report-file "$CHANGE_RECORD/import-apply.md"
)
```

Apply rejects repeated source, cutoff, target, exclusion, correction, count, strict-mode,
notification and import-user flags. It loads those values from the plan, verifies the plan
file SHA-256, then revalidates the bound source SHA-256, exact release interpreter, target,
staged IDs/counts/relationships, per-record author/post-date attribution and transactional
outcome. A new backup arriving in `SOURCE_DIRECTORY` after dry-run is ignored; apply uses
only the exact planned file. Plans from an older schema version are rejected and require a
new dry-run.

### 7. Verify the database and rendered application

```bash
"$PYTHON" "$MANAGE" shell --no-imports <<'PY'
from infrastructure_news.models import SystemStatusNews as S
from integration_news.models import IntegrationNews as I

print('system rows:', S.objects.count())
print('system null outage_id:', S.objects.filter(outage_id__isnull=True).count())
print('system relationships:', S.affected_infrastructure_items.through.objects.count())
print('system attribution:', list(S.objects.order_by('outage_id').values_list(
    'outage_id', 'author__username', 'created_at', 'published_at'
)))
print('integration rows:', I.objects.count())
print('integration null integration_news_id:', I.objects.filter(
    integration_news_id__isnull=True
).count())
print('integration relationships:', I.affected_elements.through.objects.count())
print('integration attribution:', list(I.objects.order_by(
    'integration_news_id'
).values_list(
    'integration_news_id', 'author__username', 'created_at', 'published_at'
)))
PY
```

Compare all counts, authors and timestamps with the apply report and reviewed plan. Then
manually verify representative exact-match author, fallback author, oldest, newest,
multi-resource, multi-element, empty/optional-field and HTML-heavy records through the beta
pages and both JSON APIs. Confirm the displayed Posted value is the original Drupal post
date and that no migration email or Slack notification was sent.

### 8. Repeat the rehearsal

Repeat dry-run, apply and verification at least once with the same approved release and
dump. For an exact determinism test, use a directory containing the same newest dump and
set the previous plan's exact cutoff rather than capturing a new time. Because replacement
is deterministic, the second plan and apply must produce the same row, stable-ID and
relationship counts. Preserve a new change-record directory and plan for each run.

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

Do not reuse a beta plan, plan SHA-256, report, config file or backup. Run a new strict
dry-run against the final frozen dump, review its new JSON plan and Markdown report, record
the exact plan-file SHA-256, then apply only that plan.

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
