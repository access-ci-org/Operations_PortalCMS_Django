# Database Restore Enhancement Recommendations

## Scope

This document records follow-up recommendations from the tested `portal1` restore
workflow. It is a plan for future work, not an implementation specification.

The retrieval and restore utilities should remain separate:

- `portal_db_retrieve.py` selects and downloads a specific S3 backup.
- `pg_restore_portal.sh` restores an explicitly supplied file into an explicitly
  named target database.
- The source represented by the dump and the restore target should remain visible
  as separate `--source-db` and `--target-db` arguments.

Production restores, infrastructure automation, credentials, and media replacement
remain outside the current documentation-only change.

## Validated behavior

The following behavior was validated by operator-run restores on July 27, 2026:

- The S3 object `django.portal1.dump.1785112201.gz` was retrieved and classified
  from its decompressed contents as plain SQL, producing
  `django.portal1.dump.1785112201.sql`.
- The same `portal1` dump restored successfully into both `portal_dev` and
  `portal_beta` with `--clean-restore`.
- The existing target databases were preserved. Each remained owned by
  `portal_owner`, while the replacement `portal_django` schema and its tables were
  owned by `portal_django`.
- Both targets verified with 69 tables and 47 sequences. The reported key-table
  counts matched, including 19 `auth_user` rows, 20 `cms_page` rows, and 236
  `django_migrations` rows.
- Plain SQL was correctly restored through `psql`; custom-format archives remain
  the responsibility of `pg_restore`.
- The restore refused to proceed when libpq could not find a matching password and
  succeeded after `.pgpass` contained entries matching the target database and the
  `portal_owner` and `portal_django` roles.
- The post-restore verification completed, and the final `REVOKE` confirmed removal
  of the temporary database `CREATE` privilege.

These results validate structural restoration and the verification script. They do
not by themselves prove application behavior, media consistency, or recovery from
every failure point.

## Immediate priorities: extend operator testing

Use the currently isolated `portal_dev` target for destructive testing. Keep
`portal_beta` testing coordinated with anyone using the beta application.

1. Repeat the restore with the same dump to confirm that the complete workflow is
   repeatable and leaves the same verified state.
2. Restore a different known epoch to ensure selection and source labeling do not
   depend on the already-tested filename.
3. Perform application smoke testing after a successful restore:
   - render representative public CMS pages;
   - sign in and access the administration interface;
   - inspect representative images and uploaded media;
   - exercise a small sample of integration, infrastructure, and resource views.
4. Exercise controlled pre-mutation failures:
   - missing `.pgpass` entry for `portal_owner`;
   - missing `.pgpass` entry for `portal_django`;
   - invalid credentials;
   - active target connections;
   - unexpected target database or schema ownership;
   - unreadable, truncated, or unrecognized input;
   - plain SQL containing database DDL or a psql reconnect command;
   - a plain-SQL dump that does not recreate the application schema.
5. Exercise failures during and after restoration to confirm that:
   - a transactional plain-SQL failure does not leave partially restored objects;
   - temporary `CREATE` privilege is revoked on failure;
   - verification failures are clear and return a nonzero status;
   - the documented recovery action is to correct the cause and rerun the same
     complete dump.
6. Retrieve the database and media artifacts for the same epoch. Confirm that both
   exist and can be inspected, while retaining the warning that matching filenames
   do not prove transactional consistency or successful completion of both uploads.

Record the command, source object, target, PostgreSQL client version, exit status,
verification output, and expected versus actual result for each test. Do not record
passwords, config contents, or `.pgpass` contents.

## Next priorities: improve the existing restore command

### Add a true read-only `--preflight` mode

The current `--dry-run` resolves local inputs and prints planned commands, but it
does not authenticate to the target or run all live readiness checks. Add a distinct
`--preflight` mode that performs no grants, drops, restores, or other database
mutations.

The preflight should:

- verify that the input is readable and identify plain SQL versus custom format by
  content;
- apply the existing plain-SQL checks for database DDL, reconnect commands, and
  schema completeness;
- authenticate non-interactively as both `portal_owner` and `portal_django`;
- confirm that the target exists and is not the protected source;
- report the target database owner, application schema owner, and application-role
  availability;
- report active client connections without terminating them;
- confirm that required schema and database privileges are present or identify the
  temporary privilege the real restore would need;
- show the exact source, target, format, restore strategy, verification setting,
  and credential source type without exposing credential values;
- return nonzero when the target is not ready.

Preflight logic should reuse the checks used by execution so the two paths cannot
silently drift.

### Make credential failures actionable

When libpq reports that no password was supplied, the script should explain that
`.pgpass` matching includes host, port, target database, and role. It should name
the role and target that failed without printing the password file or its contents.

Differentiate, where possible:

- no usable credential was supplied;
- authentication was attempted but rejected;
- the host or database was unreachable;
- the authenticated role lacks the required ownership or privilege.

Continue to prefer an operator-managed `PGPASSFILE`; do not accept passwords as new
command-line arguments.

### Add committed regression tests

Add tests before expanding the command surface. Use command stubs or mocks so the
suite cannot reach AWS or PostgreSQL and does not require real config or secrets.
Avoid adding a new test dependency without separate approval.

At minimum, cover:

- argument parsing and explicit source/target safety;
- content-based dump classification;
- unsafe and incomplete plain-SQL rejection;
- plain-SQL selection of `psql` and custom-format selection of `pg_restore`;
- dry-run and read-only preflight behavior;
- `.pgpass`-related error guidance for both required roles;
- active-connection and ownership refusal paths;
- cleanup of temporary privileges on success and failure;
- propagation of restore and verification failures;
- retrieval next-step output for both plain SQL and custom archives.

Tests must assert that destructive commands are not invoked in dry-run, preflight,
or rejected-input cases.

## Later priorities: improve backup evidence and operator UX

### Generate and verify a backup manifest

Generate a machine-readable manifest atomically with each backup and keep it beside
the S3 object. At minimum, record:

- source database;
- application schema;
- backup epoch and UTC creation time;
- S3 object key;
- plain-SQL or custom dump format;
- compressed and decompressed sizes where applicable;
- PostgreSQL server and `pg_dump` versions;
- SHA-256 checksum of the uploaded artifact;
- completion status;
- corresponding media object and checksum when the backup process can establish
  that relationship.

Retrieval should verify the checksum before declaring the dump ready. Restore
preflight should verify the manifest, source name, format, size, and checksum when a
manifest is available. Backward compatibility is required for older backups without
manifests, with a prominent warning rather than an inferred guarantee.

### Add a guarded convenience wrapper only after more testing

A wrapper may eventually combine selection, preflight, and execution, but it should
preserve the separation between retrieving an artifact and restoring it.

Recommended safeguards:

- default to read-only preflight;
- require `--execute` before mutation;
- require the operator to confirm the exact target name interactively, or supply a
  separate exact-match confirmation flag for approved automation;
- print the source object, epoch, target, format, destructive scope, active
  connections, and manifest result immediately before execution;
- refuse `portal1` by default;
- never infer a target from the source filename;
- retain an option to run retrieval and restoration as separate commands.

Do not build the wrapper until the controlled-failure tests identify which recovery
messages and cleanup guarantees operators actually need.

### Harden the external backup producer separately

Future work in
`Operations_Warehouse_Management-Tools/sbin/backup_portal.sh` should remain a
separate, explicitly approved cross-repository change. The backup producer must not
invoke a restore wrapper.

Potential hardening includes:

- fail-fast shell behavior and consistent quoting;
- checking `pg_dump`, compression, checksum, and upload results independently;
- uploading the dump and manifest in an order that cannot advertise an incomplete
  backup as ready;
- validating the uploaded object before deleting local staging files;
- recording format, schema scope, versions, sizes, and checksums;
- keeping database and media retention rules explicitly scoped;
- testing the seven-day threshold as exactly seven 24-hour periods
  (`604800` seconds) and defining boundary behavior;
- emitting useful monitoring output without exposing credentials.

Any change to retention, S3 deletion, infrastructure scheduling, or the external
repository requires its own review and authorization.

## Assumptions and constraints

- `portal1` is the protected source database and system of record.
- `portal_dev` and `portal_beta` are non-production targets, but they can still have
  active users or applications and should be isolated during restoration.
- The desired target state matches the selected dump, not the live state of
  `portal1` at restore time.
- The normal refresh preserves the target database and replaces the application
  schema; `--recreate-db` is not required.
- Plain SQL must continue to use `psql`, and custom archives must continue to use
  `pg_restore`.
- Media recovery is a separate operation and currently merges files rather than
  deleting unrelated target files.
- Credentials must remain outside source control and command history.
- No production restore, migration, infrastructure action, or automated retention
  change is implied by these recommendations.

## Unresolved risks

- A checksum detects changed bytes but not a logically incomplete source backup.
- A connection can appear after preflight and before execution; target application
  isolation remains necessary.
- The current plain-SQL preparation can remove a maintenance-owned schema before the
  transactional application-role restore begins. A later failure can therefore
  leave the non-production target without that schema until the complete dump is
  rerun.
- Matching database and media epochs do not guarantee a transactionally consistent
  recovery point.
- Structural verification does not replace application-level smoke testing.
- PostgreSQL client/server version compatibility and cross-version restore policy
  still need to be defined and tested.
- A convenience wrapper could conceal destructive scope if it reduces the
  visibility of the underlying commands; safety and explicitness take priority over
  fewer keystrokes.
