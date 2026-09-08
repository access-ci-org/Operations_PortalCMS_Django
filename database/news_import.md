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

This procedure deliberately avoids a shell-wide `set -e` and top-level `exit`. Each phase
is a function: a failed check prints `STOP`, returns to the `software` prompt, and leaves
the rehearsal variables available for inspection with `news_state`. Run one phase at a
time and do not continue after a nonzero return. Paste only fenced command blocks; prose
such as “review” or “then” is not a shell command.

### 1. Prerequisites

Before starting:

- deploy the approved immutable release through the normal infrastructure workflow;
- place one or more readable, timestamp-named MySQL dumps in
  `/soft/django-cms-01/var/news-import`;
- independently confirm the beta database name and PostgreSQL write endpoint;
- obtain separate approval for the beta database replacement; and
- confirm that `jlambertson` is the approved fallback Django user.

The dump directory selector accepts only readable regular files named
`backup_database-<timezone-aware-ISO-timestamp>.mysql.gz`. It selects the newest timestamp
in the filename, not the file modification time. Apply never rescans the directory; the
selected absolute path and SHA-256 are bound into the dry-run plan.

### 2. Start one `software` shell and initialize the run

Start a clean login shell:

```bash
sudo -i -u software
```

Paste this function block. Do not enable `set -e` in the login shell.

```bash
set +e
set +u

news_fail() {
  printf 'STOP: %s\n' "$*" >&2
  return 1
}

news_require() {
  local description="$1"
  shift
  if ! "$@"; then
    news_fail "$description"
    return 1
  fi
}

news_state() {
  printf 'Release: %s\n' "${RELEASE:-<unset>}"
  printf 'Python: %s\n' "${PYTHON:-<unset>}"
  printf 'Cutoff: %s\n' "${SYSTEM_NEWS_AS_OF:-<unset>}"
  printf 'Evidence directory: %s\n' "${CHANGE_RECORD:-<unset>}"
  printf 'Plan: %s\n' "${IMPORT_PLAN:-<unset>}"
  printf 'Target backup: %s\n' "${TARGET_BACKUP:-<unset>}"
}

news_setup() {
  local release_name="${1:-}"
  local requested_cutoff="${2:-}"

  case "$release_name" in
    ''|*'<'*|*'>'*|*/*)
      news_fail 'pass the exact release directory name, without angle brackets or slashes'
      return 1
      ;;
  esac

  umask 027

  APP_HOME=/soft/django-cms-01
  RELEASE="$APP_HOME/releases/$release_name"
  PYTHON="$RELEASE/.venv/bin/python"
  MANAGE="$RELEASE/operations_portalcms_django/manage.py"
  BACKUP_SCRIPT="$RELEASE/database/pg_dump_portal.sh"
  APP_CONFIG="$APP_HOME/conf/portal.conf"

  SOURCE_DIRECTORY="$APP_HOME/var/news-import"
  EXPECTED_DATABASE=portal_beta
  EXPECTED_WRITE_HOST=opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com
  IMPORT_USER=jlambertson

  RUN_ID="$(date -u '+%Y%m%dT%H%M%SZ')"
  CHANGE_RECORD="$APP_HOME/var/news-import/beta-rehearsal-$RUN_ID"
  IMPORT_PLAN="$CHANGE_RECORD/import-plan.json"
  DRY_RUN_REPORT="$CHANGE_RECORD/import-dry-run.md"
  PRETTY_PLAN="$CHANGE_RECORD/import-plan.pretty.json"
  PLAN_CHECKSUM_FILE="$CHANGE_RECORD/import-plan.sha256"
  APPLY_REPORT="$CHANGE_RECORD/import-apply.md"
  TARGET_BACKUP="$CHANGE_RECORD/portal_beta_pre_import.dump"
  BACKUP_CHECKSUM_FILE="$CHANGE_RECORD/target-backup.sha256"
  if test -n "$requested_cutoff"; then
    SYSTEM_NEWS_AS_OF="$requested_cutoff"
  else
    SYSTEM_NEWS_AS_OF="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
  fi

  export APP_CONFIG RELEASE EXPECTED_DATABASE EXPECTED_WRITE_HOST
  export IMPORT_USER CHANGE_RECORD IMPORT_PLAN

  news_require 'the operating-system user is not software' \
    test "$(id -un)" = software || return 1
  news_require 'release Python is missing or not executable' \
    test -x "$PYTHON" || return 1
  news_require 'manage.py is missing or unreadable' \
    test -r "$MANAGE" || return 1
  news_require 'APP_CONFIG is missing or unreadable' \
    test -r "$APP_CONFIG" || return 1
  news_require 'source directory does not exist' \
    test -d "$SOURCE_DIRECTORY" || return 1
  news_require 'source directory is not readable/searchable' \
    test -r "$SOURCE_DIRECTORY" || return 1
  news_require 'source directory is not readable/searchable' \
    test -x "$SOURCE_DIRECTORY" || return 1

  if ! mkdir -m 0750 "$CHANGE_RECORD"; then
    news_fail "could not create evidence directory: $CHANGE_RECORD"
    return 1
  fi
  news_require 'evidence directory is not writable' \
    test -w "$CHANGE_RECORD" || return 1

  news_state
  printf 'Setup checks: OK\n'
}
```

Run setup, replacing only the release directory name:

```bash
news_setup \
  '<NEW-EXACT-RELEASE>'
```
# EXAMPLE formatting
```bash
news_setup \
  'news_apis_imports_testing-4e65ccf8baef-19d6e816f90f-1788866946'
```

Keep this shell open and do not redefine the variables. Do not export `PYTHONPATH`.
For a deterministic replay only, pass the previously reviewed cutoff as a second argument
to `news_setup`; otherwise setup captures the current UTC time exactly once.

### 3. Confirm the importer release and target

Define and run the preflight function:

```bash
news_preflight() {
  local help_text option

  news_require 'run news_setup first' test -n "${PYTHON:-}" || return 1

  if ! help_text="$("$PYTHON" "$MANAGE" import_drupal_news --help 2>&1)"; then
    printf '%s\n' "$help_text" >&2
    news_fail 'could not read importer help'
    return 1
  fi

  for option in \
    --mysql-dump-directory \
    --plan-file \
    --confirm-plan-sha256
  do
    if ! grep -Fq -- "$option" <<<"$help_text"; then
      news_fail "release does not support $option"
      return 1
    fi
  done

  if ! "$PYTHON" "$MANAGE" shell --no-imports <<'PY'
import os
import sys
from pathlib import Path

from django.conf import settings
from django.contrib.auth.models import User
from infrastructure_news.management.commands.import_drupal_news import (
    IMPORT_CONTRACT_VERSION,
    IMPORT_PLAN_VERSION,
)

database = settings.DATABASES["default"]
expected_python = Path(os.environ["RELEASE"]) / ".venv/bin/python"

print("python:", sys.executable)
print("plan version:", IMPORT_PLAN_VERSION)
print("contract version:", IMPORT_CONTRACT_VERSION)
print("database:", database.get("NAME"))
print("write host:", database.get("HOST"))
print("port:", database.get("PORT"))
print("fallback user:", os.environ["IMPORT_USER"])

if Path(sys.executable) != expected_python:
    raise SystemExit("Python executable does not match RELEASE")
if (IMPORT_PLAN_VERSION, IMPORT_CONTRACT_VERSION) != (3, 3):
    raise SystemExit("Release does not contain plan/contract version 3")
if str(database.get("NAME") or "") != os.environ["EXPECTED_DATABASE"]:
    raise SystemExit("Database does not match EXPECTED_DATABASE")
if str(database.get("HOST") or "") != os.environ["EXPECTED_WRITE_HOST"]:
    raise SystemExit("Host does not match EXPECTED_WRITE_HOST")
if not User.objects.filter(username=os.environ["IMPORT_USER"]).exists():
    raise SystemExit("Fallback Django user does not exist")

print("Release and target checks: OK")
PY
  then
    news_fail 'release or target preflight failed; inspect the output above'
    return 1
  fi
}

news_preflight
```

This reads settings but never prints credentials. Continue only after the output confirms
plan and contract version 3, the release interpreter, `portal_beta`, the independently
approved beta write host, and fallback user `jlambertson`.

### 4. Run the strict dry-run

```bash
news_dry_run() {
  news_require 'run news_setup first' test -n "${IMPORT_PLAN:-}" || return 1
  news_require 'the import plan path already exists' \
    test ! -e "$IMPORT_PLAN" || return 1

  if test -e "$DRY_RUN_REPORT"; then
    DRY_RUN_REPORT="$CHANGE_RECORD/import-dry-run-retry-$(date -u '+%Y%m%dT%H%M%SZ').md"
    printf 'Preserving the earlier report; retry report: %s\n' "$DRY_RUN_REPORT"
  fi

  if ! "$PYTHON" "$MANAGE" import_drupal_news \
    --mysql-dump-directory "$SOURCE_DIRECTORY" \
    --replace \
    --dry-run \
    --strict \
    --suppress-notifications \
    --system-news-as-of "$SYSTEM_NEWS_AS_OF" \
    --exclude-system-nid 404 \
    --exclude-system-nid 797 \
    --source-correction infrastructure-928-start-year \
    --confirm-database "$EXPECTED_DATABASE" \
    --confirm-host "$EXPECTED_WRITE_HOST" \
    --plan-file "$IMPORT_PLAN" \
    --report-file "$DRY_RUN_REPORT" \
    --import-user "$IMPORT_USER"
  then
    news_fail "dry-run failed; inspect $DRY_RUN_REPORT if it exists"
    return 1
  fi

  news_require 'dry-run did not create a nonempty plan' \
    test -s "$IMPORT_PLAN" || return 1
  news_require 'dry-run did not create a nonempty report' \
    test -s "$DRY_RUN_REPORT" || return 1

  if ! "$PYTHON" -m json.tool "$IMPORT_PLAN" > "$PRETTY_PLAN"; then
    news_fail 'plan JSON validation/formatting failed'
    return 1
  fi

  printf 'Dry-run artifacts: OK\n'
  printf 'MANDATORY PAUSE: review the plan and report before backup or apply.\n'
  news_state
}

news_dry_run
```

The importer chooses the newest valid dump and records its exact path and SHA-256, cutoff,
retained IDs, counts, relationships, exclusions, correction, author/post-date attribution,
and planned database outcome. If a newer dump was selected than intended, stop and start a
new rehearsal with a controlled source directory.

### 5. Mandatory review pause

Open the human-readable report and, optionally, the complete formatted plan:

```bash
less "$DRY_RUN_REPORT"
less "$PRETTY_PLAN"
```

Print and validate the compact version 3 contract:

```bash
news_review_contract() {
  if ! "$PYTHON" - "$IMPORT_PLAN" <<'PY'
import json
import sys
from pathlib import Path

plan = json.loads(Path(sys.argv[1]).read_text())
contract = plan["contract"]
expected = plan["expected"]

if plan["schema"] != "access-ci.drupal-news-import-plan":
    raise SystemExit("Unexpected plan schema")
if (plan["version"], contract["contract_version"]) != (3, 3):
    raise SystemExit("Expected plan/contract version 3")

fallback_user = contract["options"]["import_user"]
for feed, key in (
    ("SystemStatusNews", "system_attribution"),
    ("IntegrationNews", "integration_attribution"),
):
    values = expected[key]
    for item in values:
        if not item["posted_at"]:
            raise SystemExit(f"{feed} nid={item['nid']} has no posted_at")
        if "@" in item["username_candidate"]:
            raise SystemExit(f"{feed} contains an email-shaped username candidate")
        if (
            item["resolution"] == "fallback"
            and item["django_username"] != fallback_user
        ):
            raise SystemExit(f"{feed} fallback does not use {fallback_user}")

print("schema:", plan["schema"])
print("plan/contract version:", plan["version"], contract["contract_version"])
print("python:", contract["python_executable"])
print("source:", contract["source"]["path"])
print("source SHA-256:", contract["source"]["sha256"])
print("database/host/port:", contract["target"])
print("fallback user:", fallback_user)
print("cutoff:", contract["adjustments"]["system_news_as_of"])
print("explicit exclusions:", contract["adjustments"]["excluded_system_nids"])
print("corrections:", contract["adjustments"]["source_corrections"])
print("system IDs:", expected["system_ids"])
print("integration IDs:", expected["integration_ids"])
print("cutoff-excluded system IDs:", expected["cutoff_excluded_system_nids"])
print("system relationships:", expected["system_relationships"])
print("integration relationships:", expected["integration_relationships"])
print("planned outcome:", expected["outcome"])

for feed, key in (
    ("SystemStatusNews", "system_attribution"),
    ("IntegrationNews", "integration_attribution"),
):
    values = expected[key]
    matched = sum(item["resolution"] == "drupal-username" for item in values)
    fallbacks = [item for item in values if item["resolution"] == "fallback"]
    print(f"{feed} attribution: {matched} exact, {len(fallbacks)} fallback")
    for item in fallbacks:
        print(
            f"  nid={item['nid']} uid={item['drupal_uid']} "
            f"candidate={item['username_candidate']!r} "
            f"derivation={item['username_derivation']} "
            f"Django={item['django_username']!r} "
            f"reason={item['fallback_reason']} "
            f"posted={item['posted_at']}"
        )
PY
  then
    news_fail 'plan contract review failed'
    return 1
  fi
}

news_review_contract
```

Do not continue until a human confirms all of the following:

- the selected source path and SHA-256 identify the intended dump;
- the Python executable, database, write host, fallback user and cutoff are exact;
- only operationally appropriate current/future Infrastructure News IDs are retained;
- explicit exclusions are exactly `404` and `797`, and the only correction is nid `928`;
- relationship and planned delete/create counts are sensible;
- every post date and exact username match in the full report is correct;
- every fallback is understood and resolves to `jlambertson`; and
- the report contains zero importer warnings and zero importer errors.

The Django Treebeard compatibility warning is separate from the importer report. A dry-run
rolls back, so querying PostgreSQL at this point shows the existing rows rather than the
staged replacement.

### 6. Preview and take the separately approved beta backup

The backup is a separate database operation and requires its own human authorization. Its
script runs as a child process, so its internal `exit` cannot close the login shell. First
preview the resolved database, host and output without taking a backup:

```bash
news_backup_preview() {
  news_require 'backup script is missing or not executable' \
    test -x "$BACKUP_SCRIPT" || return 1
  news_require 'target backup path already exists' \
    test ! -e "$TARGET_BACKUP" || return 1

  if ! "$BACKUP_SCRIPT" \
    --source-db "$EXPECTED_DATABASE" \
    --output "$TARGET_BACKUP" \
    --dry-run
  then
    news_fail 'backup preview failed'
    return 1
  fi
}

news_backup_preview
```

The preview must show the independently approved beta database and host. If the backup
script's configured read host is not that approved target, stop; do not override or infer a
different endpoint during the change.

After visually confirming the preview and obtaining the separate backup approval, run:

```bash
news_backup() {
  if test "${1:-}" != CREATE_BETA_BACKUP; then
    news_fail 'call: news_backup CREATE_BETA_BACKUP'
    return 1
  fi
  news_require 'target backup path already exists' \
    test ! -e "$TARGET_BACKUP" || return 1

  if ! "$BACKUP_SCRIPT" \
    --source-db "$EXPECTED_DATABASE" \
    --output "$TARGET_BACKUP"
  then
    news_fail 'beta backup failed'
    return 1
  fi

  news_require 'beta backup is missing or empty' \
    test -s "$TARGET_BACKUP" || return 1
  if ! sha256sum "$TARGET_BACKUP" > "$BACKUP_CHECKSUM_FILE"; then
    news_fail 'could not write the backup checksum'
    return 1
  fi
  if ! sha256sum --check "$BACKUP_CHECKSUM_FILE"; then
    news_fail 'backup checksum verification failed'
    return 1
  fi

  printf 'Beta backup: OK\n'
  printf 'Backup: %s\n' "$TARGET_BACKUP"
}

news_backup CREATE_BETA_BACKUP
```

### 7. Bind and apply only the reviewed plan

Record and verify the plan checksum only after review and backup:

```bash
news_prepare_apply() {
  news_require 'reviewed plan is missing or empty' \
    test -s "$IMPORT_PLAN" || return 1
  news_require 'beta backup is missing or empty' \
    test -s "$TARGET_BACKUP" || return 1
  news_require 'backup checksum record is missing' \
    test -s "$BACKUP_CHECKSUM_FILE" || return 1
  if ! sha256sum --check "$BACKUP_CHECKSUM_FILE"; then
    news_fail 'backup checksum verification failed'
    return 1
  fi
  if ! sha256sum "$IMPORT_PLAN" > "$PLAN_CHECKSUM_FILE"; then
    news_fail 'could not write the plan checksum'
    return 1
  fi
  if ! sha256sum --check "$PLAN_CHECKSUM_FILE"; then
    news_fail 'plan checksum verification failed'
    return 1
  fi

  PLAN_SHA256="$(awk '{print $1}' "$PLAN_CHECKSUM_FILE")"
  export PLAN_SHA256
  news_require 'plan SHA-256 is empty' test -n "$PLAN_SHA256" || return 1
  printf 'Reviewed plan SHA-256: %s\n' "$PLAN_SHA256"
}

news_prepare_apply
```

Apply requires a final explicit phrase and refuses to overwrite an existing apply report:

```bash
news_apply() {
  if test "${1:-}" != APPLY_BETA_NEWS_IMPORT; then
    news_fail 'call: news_apply APPLY_BETA_NEWS_IMPORT'
    return 1
  fi
  news_require 'run news_prepare_apply first' \
    test -n "${PLAN_SHA256:-}" || return 1
  news_require 'an apply report already exists' \
    test ! -e "$APPLY_REPORT" || return 1
  if ! sha256sum --check "$PLAN_CHECKSUM_FILE"; then
    news_fail 'reviewed plan changed after checksum creation'
    return 1
  fi

  if ! "$PYTHON" "$MANAGE" import_drupal_news \
    --apply \
    --plan-file "$IMPORT_PLAN" \
    --confirm-plan-sha256 "$PLAN_SHA256" \
    --report-file "$APPLY_REPORT"
  then
    news_fail "apply failed; inspect $APPLY_REPORT if it exists"
    return 1
  fi

  news_require 'apply did not create a nonempty report' \
    test -s "$APPLY_REPORT" || return 1
  printf 'Apply: OK\n'
  printf 'Apply report: %s\n' "$APPLY_REPORT"
}

news_apply APPLY_BETA_NEWS_IMPORT
```

Do not repeat source, cutoff, exclusion, correction, target, count, notification or import
user options during apply. They come from the reviewed plan. A newer dump arriving after
dry-run is ignored.

### 8. Verify the applied rows

Review the complete apply report, then query both feeds:

```bash
less "$APPLY_REPORT"
```

```bash
news_verify() {
  if ! "$PYTHON" "$MANAGE" shell --no-imports <<'PY'
from infrastructure_news.models import SystemStatusNews as S
from integration_news.models import IntegrationNews as I

print("system rows:", S.objects.count())
print("system null outage_id:", S.objects.filter(outage_id__isnull=True).count())
print("system relationships:", S.affected_infrastructure_items.through.objects.count())
print("system attribution:")
for row in S.objects.order_by("outage_id").values_list(
    "outage_id", "author__username", "created_at", "published_at"
):
    print(" ", row)

print("integration rows:", I.objects.count())
print(
    "integration null integration_news_id:",
    I.objects.filter(integration_news_id__isnull=True).count(),
)
print("integration relationships:", I.affected_elements.through.objects.count())
print("integration attribution:")
for row in I.objects.order_by("integration_news_id").values_list(
    "integration_news_id", "author__username", "created_at", "published_at"
):
    print(" ", row)
PY
  then
    news_fail 'post-apply database verification failed'
    return 1
  fi
}

news_verify
```

Confirm counts, relationships, authors and timestamps against the reviewed plan and apply
report. Manually check representative exact-match, fallback, multi-resource,
multi-element and HTML-heavy records in both beta pages and JSON APIs. Confirm displayed
post dates are the Drupal dates and that no migration email or Slack notification was
sent.

### 9. Failure and retry behavior

When any phase prints `STOP`, remain in the same shell, run `news_state`, inspect the
reported artifact, correct the cause, and rerun only that phase. The functions never call
top-level `exit`, so they do not log out `software`, and their global rehearsal variables
remain set. Do not retry a failed or uncertain apply until its report and database outcome
are understood. Use a new evidence directory and a new dry-run if any reviewed input,
release, target, source dump, cutoff, user resolution or correction changes.

If the login shell itself is closed or disconnected, its variables and functions cannot
be recovered from Bash. Start a new `software` shell and either begin a new rehearsal or
restore the exact release and evidence paths from the successful dry-run before doing any
further work; never guess paths from an older run.

Repeat the full rehearsal after any code change, new dump, dependency-lock change or target
configuration change. For a determinism test, use the same newest dump and call
`news_setup '<NEW-EXACT-RELEASE>' '<PRIOR-PLAN-CUTOFF>'`, but always create a new evidence
directory and plan.

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
