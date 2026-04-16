# CMS Versioning And Moderation Rollout Plan

Historical note:

- On 2026-04-06, the validated clone database was promoted into the canonical `portalcms1` name.
- The former `portalcms1` database was renamed to `portalcms1_old`.
- On 2026-04-07, the live runtime was cut over again from local PostgreSQL to Amazon RDS database `portal1`.
- References to `portalcms1_clone`, `portal-clone.service`, and `portal-clone.socket` below describe the validation and rollout path that led to the current standard environment.
- The temporary clone-specific runtime files used during validation were retired after the cutover.
- Some historical file paths below no longer exist in the repo or active runtime; they are retained as rollout notes only.

## Purpose

This document is the historical rollout plan that was used for introducing real Django CMS
draft/review/publish behavior for focus-area pages.

It is intentionally more detailed than `CMS_VERSIONING_SKETCH.md` and remains
useful as a historical runbook for understanding how the clone-first validation was completed.

## Current State Summary

As of 2026-04-03:

- focus-area pages now use Django CMS placeholders/plugins only
- legacy `FocusAreaSection` code, permissions, and database rows have been retired
- the database schema has been migrated through
  `operations_portalcms_django.0017_delete_focusareasection`
- a fresh safety dump exists at:
  - `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/portalcms1_post_migrate_20260401T185011Z.dump`
- a legacy content archive exists at:
  - `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/focus_area_sections_archive_20260401.json`
- the codebase now installs and configures:
  - `djangocms_versioning`
- the codebase still does **not** enable:
  - `djangocms_moderation`

Important complication:

- the live database still contains stranded old `djangocms_versioning_*` and
  `djangocms_moderation_*` history
- the clone database was refreshed, cleaned, re-migrated for versioning, and re-bootstrapped
- this remained a reconciliation and repair rollout, not a clean first install

Validated clone result:

- `portalcms1_clone` now has working django CMS page versioning
- STEP was tested through the browser with:
  - a page-specific editor creating a new draft
  - a reviewer/superuser publishing the new version
- the clone DB ended with:
  - 19 `cms_pagecontent` rows
  - 19 `djangocms_versioning_version` rows
  - states `published:18, unpublished:1`
- the normal public dev hostname `cms2.operations.access-ci.org` was temporarily repointed to the clone socket for browser testing

## Goal

Achieve true page-level moderated workflow for focus-area CMS content:

1. page-specific editor creates draft changes
2. public site keeps showing last published content
3. `Focus_area_editors` reviews and publishes
4. production content remains intact throughout rollout

## Non-Goals

The following are out of scope for the first rollout:

- introducing a second section-level content model
- custom workflow for non-CMS models
- broad content rewrites
- navigation redesign
- migration squashing
- touching the live site before the clone path is proven

## Key Constraints

### Technical Constraints

- versioning is not yet installed in code
- old versioning/moderation schema artifacts already exist in the DB
- public page content must remain unchanged during the rollout
- focus-area content must stay on the CMS page-content path only

### Operational Constraints

- clone-first only
- backup before any destructive or schema-changing step
- explicit database targeting on every command
- no mixing versioning rollout with unrelated refactors

## Source Files And Inputs

### Primary Planning Inputs

- [CMS_VERSIONING_SKETCH.md](./CMS_VERSIONING_SKETCH.md)
- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/memory/clone_versioning_handoff.txt`

### Current Safety Artifacts

- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/portalcms1_post_migrate_20260401T185011Z.dump`
- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/focus_area_sections_archive_20260401.json`

### Historical Clone Config Used During Validation

- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/portal.conf.clone.json`

### Current Database Scripts

- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/database/pg_dump_cms.sh`
- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/database/pg_restore_cms.sh`
- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/database/clone_db.sh`
- `/soft/django-cms-01/tags/Operations_PortalCMS_Django/database/verify_db.sh`

## Recommended Strategy

Use a clone-first reconciliation strategy.

Recommended order:

1. rebuild or refresh clone from the newest post-migration dump
2. verify that the clone app config truly points to the clone DB
3. inspect the stranded old versioning/moderation state in clone
4. choose a reconciliation strategy in clone
5. install/configure versioning in code
6. run migrations in clone
7. bootstrap current CMS page content as initial published baseline
8. validate browser and permission behavior in clone
9. only then prepare a production runbook

Current status:

- phases 1 through 7 have been proven in clone for the STEP workflow using versioning only
- moderation has not been enabled
- the next major decision is whether broader testing is enough to stop at versioning, or whether a stricter moderation layer is still required

## Phase Plan

### Phase 0: Preflight Baseline

Objective:

- confirm that code, schema, and safety backups are aligned before the
  versioning work starts

Checklist:

1. confirm current backup file exists
2. confirm legacy section archive exists
3. confirm focus pages render from CMS placeholders/plugins only
4. confirm `0017_delete_focusareasection` has been applied
5. confirm no local unreviewed schema drift remains

Success criteria:

- schema and code are aligned
- fresh safety backup exists
- focus-area content path is simplified to CMS page content only

### Phase 1: Refresh The Clone

Objective:

- create a clean test environment based on the newest known-good dump

Recommended actions:

1. restore the fresh dump into `portalcms1_clone`
2. run `verify_db.sh` against the clone DB
3. confirm page counts and migration counts look sane
4. confirm clone config still points to `portalcms1_clone`

Success criteria:

- clone DB exists
- clone DB reflects the newest schema and data state
- clone app config points at the clone DB, not the live DB

Failure criteria:

- app config drift
- missing CMS tables
- migration history mismatch

Fallback:

- recreate the clone from the dump again rather than trying to patch a bad clone

### Phase 2: Versioning And Moderation Inventory

Objective:

- understand exactly what stranded old versioning/moderation state exists in the clone

Required inventory:

1. row counts in:
   - `djangocms_versioning_version`
   - `djangocms_versioning_statetracking`
   - all `djangocms_moderation_*` tables
2. `django_migrations` rows related to:
   - `djangocms_versioning`
   - `djangocms_moderation`
3. all current `cms_pagecontent` rows
4. which `cms_pagecontent` rows already have version rows
5. which version rows are stale relative to current `cms_pagecontent`

Specific questions to answer:

- are all version rows for `cms.pagecontent` only?
- which `cms_pagecontent` rows are missing version rows?
- are there stale draft rows that no longer match current live content?
- do the moderation tables contain anything operationally meaningful, or only stranded history?

Success criteria:

- exact inventory is written down
- the team understands whether cleanup-first or revive-first is safer

### Phase 3: Choose Reconciliation Path

There are two candidate paths.

#### Preferred Path: Cleanup-First

Use this if the old versioning/moderation state appears partial, stale, or unsafe.

Approach:

1. in clone only, remove or neutralize stranded versioning/moderation state
2. add the packages in code/settings
3. run official package migrations
4. bootstrap fresh version rows from current `cms_pagecontent`

Advantages:

- cleaner mental model
- lower risk of reviving broken/stale historical rows
- easier to reason about as a new baseline

Risks:

- if cleanup is incomplete, package migrations may still collide with old schema/state

#### Fallback Path: Revive-First

Use this only if the old state appears mostly consistent and repairable.

Approach:

1. add the packages in code/settings in clone
2. run or fake required migrations carefully
3. repair missing version rows
4. reconcile stale version state against current content

Advantages:

- preserves more historical state if that matters

Risks:

- harder to reason about
- easier to preserve broken assumptions
- greater chance of partial success with hidden inconsistencies

Recommendation:

- prefer cleanup-first unless inventory reveals a strong reason not to

### Phase 4: Code And Package Enablement

Objective:

- add the actual versioning/moderation packages in code in a controlled way

Expected work items:

1. add package dependencies
2. register apps in `INSTALLED_APPS`
3. configure any required CMS versioning integration
4. confirm supported versions against current `django-cms` version

Guardrails:

- do this only after the clone inventory is complete
- do not make production environment changes yet

Open technical question:

- whether both `djangocms_versioning` and `djangocms_moderation` are needed, or whether
  versioning alone plus current group permissions is sufficient for the first rollout

### Phase 5: Schema Migration In Clone

Objective:

- apply the package schema in the clone DB only

Required pre-checks:

1. capture table counts before migrations
2. capture row counts in CMS content tables
3. record current page titles and pagecontent row counts

Required post-checks:

1. migrations complete without table loss
2. CMS page counts match before/after
3. `cms_pagecontent` counts match before/after
4. placeholder/plugin counts match before/after

If counts drift unexpectedly:

- stop immediately
- inspect clone DB before proceeding
- restore clone from dump if necessary

### Phase 6: Bootstrap Initial Published Versions

Objective:

- turn current live CMS content into the initial version baseline

Desired outcome:

- every current focus-area-relevant `cms_pagecontent` row gets an initial version record
- that record represents the current published/live state
- future edits create true draft versions instead of changing the live state directly

Key rule:

- current visible page content should become version 1 / published baseline

Validation questions:

- does every relevant `cms_pagecontent` row now have a version row?
- do version counts match expected pagecontent coverage?
- is public rendering unchanged?

### Phase 7: Workflow Validation In Clone

Objective:

- prove the workflow works for real in the clone environment

Minimum workflow test:

1. log in as page-specific editor
2. edit one focus page in CMS
3. save changes
4. verify public page still shows old published content
5. log in as `Focus_area_editors`
6. review and publish
7. verify public page now shows the updated content

Minimum user matrix:

- one page-specific editor
- one `Focus_area_editors` reviewer/publisher
- one anonymous browser session

Go criteria:

- public rendering remains stable before publish
- draft changes are held back
- reviewer can publish successfully

No-go criteria:

- edits still go live immediately
- content disappears
- version rows are incomplete
- publish actions fail for reviewer role

### Phase 8: Production Runbook Preparation

Do not touch production until all previous phases succeed.

The production runbook should contain:

1. exact DB target verification
2. fresh pre-change backup
3. pre-change counts
4. package deployment steps
5. migration steps
6. bootstrap steps
7. smoke-test steps
8. rollback plan using the fresh dump

## Command Categories To Prepare

These are the command categories the next session should expect to use:

### Clone Refresh

- dump restore to `portalcms1_clone`
- clone DB verification
- app config verification

### Inventory

- SQL or Django shell queries against:
  - `cms_pagecontent`
  - `djangocms_versioning_*`
  - `djangocms_moderation_*`
  - `django_migrations`

### Package Enablement

- dependency install
- settings update
- Django migrations

### Validation

- Django shell permission checks
- browser/UI checks against the clone-backed app instance

## Risk Register

### Risk 1: Wrong Database Target

Description:

- the project supports multiple config sources and can silently point at the wrong DB

Mitigation:

- always print resolved DB name before migrations
- use explicit `APP_CONFIG` for clone work

### Risk 2: Stranded Historical Versioning State

Description:

- existing old versioning tables and rows may conflict with a new rollout

Mitigation:

- inventory first
- reconcile in clone only
- prefer cleanup-first if state is stale

### Risk 3: Apparent “Database Reset”

Description:

- wrong DB target or mismatched bootstrap assumptions can make the site look empty

Mitigation:

- backup first
- pre/post counts
- clone-only experiments first

### Risk 4: Public Content Drift

Description:

- schema or bootstrap work may accidentally alter visible content

Mitigation:

- compare public rendering before and after
- inspect placeholder/plugin counts

## Go / No-Go Gates

### Go To Package Installation Only If

- clone is verified
- inventory is complete
- reconciliation strategy is chosen

### Go To Bootstrap Only If

- package migrations succeed in clone
- pagecontent and plugin counts match expected values

### Go To Production Planning Only If

- clone workflow works end-to-end
- public rendering is unchanged until publish
- reviewer publish works reliably

## Migration Squashing Guidance

Do **not** squash migrations now.

Reason:

- the versioning rollout will likely add more migrations
- squashing now would create unnecessary churn before the schema stabilizes

Recommended timing:

1. complete versioning/moderation rollout
2. stabilize schema across environments
3. then evaluate `squashmigrations`

Preferred cleanup method later:

- squash, do not rewrite migration history abruptly

## Immediate Next-Step Set

This is the recommended order for the next hands-on session:

1. refresh `portalcms1_clone` from the fresh post-migration dump
2. verify clone DB and clone config targeting
3. inventory stranded `djangocms_versioning_*` and `djangocms_moderation_*` state in clone
4. choose cleanup-first or revive-first
5. only then touch dependencies and settings

## Definition Of Done For This Rollout

The first versioning rollout is complete when:

- focus-area content remains CMS-page-content only
- the clone environment supports true draft/review/publish behavior
- page-specific editors cannot publish
- `Focus_area_editors` can publish
- public content does not change until publish
- production rollout steps are documented and reversible
