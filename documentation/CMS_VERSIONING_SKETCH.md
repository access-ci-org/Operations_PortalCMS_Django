# CMS Versioning Sketch

## Purpose

Sketch a safe path to introduce real Django CMS draft/review/publish behavior for focus-area pages without repeating the prior "database reset" incident.

For the current detailed execution plan, see:

- [CMS_VERSIONING_ROLLOUT_PLAN.md](./CMS_VERSIONING_ROLLOUT_PLAN.md)

## Current Findings

Historical findings verified in the live app state on 2026-03-31:

- `jlambertson` is only in `Focus_STEP_Editors`
- STEP `PagePermission` is `can_change=True`, `can_publish=False`
- `Page.has_publish_permission(jlambertson)` returns `False`
- project is using `django-cms==5.0.5`
- `djangocms_versioning` is not installed

Historical conclusion at that time:

- Current focus-area behavior is not backed by true CMS content versioning
- page edit vs publish permissions alone are not enough to create a real moderation workflow here
- if we want draft/review/publish for CMS page content, CMS versioning support is required

Current status as of 2026-04-24:

- `djangocms_versioning` is installed and active in the RDS-backed runtime.
- `djangocms_moderation` is not enabled.
- RDS `portal1` has 26 CMS version rows: 18 `published`, 8 `unpublished`.
- Focus-area page permissions are configured so page-specific groups can edit but not publish, while `Focus_area_editors` can edit and publish.
- See [CURRENT_STATE.md](./CURRENT_STATE.md) for the current verification snapshot.

## Why Edits Still Go Live

Without CMS versioning, editing a CMS page changes the active content directly.

That means:

- `can_publish=False` may hide publish actions
- but there is no separate moderated draft content stream to hold unpublished changes
- so "edit but not publish" is not a complete workflow by itself

This explains the observed mismatch:

- permissions look correct
- but edits still become visible immediately

## Desired Workflow Logic

For focus-area pages:

1. Page-specific editor opens page content in CMS edit mode
2. editor saves a draft version
3. public page continues showing the last published version
4. reviewer in `Focus_area_editors` opens the draft
5. reviewer either edits further, rejects out-of-band, or publishes
6. publish action promotes the reviewed version live

Role logic:

- `Focus_STEP_Editors` and other page-specific groups:
  - can create and edit draft versions for their assigned pages
  - cannot publish
- `Focus_area_editors`:
  - can edit drafts
  - can publish reviewed versions
- superusers:
  - full override

## Legacy Managed Section Status

The legacy `FocusAreaSection` path has now been retired from active focus-area rendering and cleaned out of the database.

Current direction:

- focus-area content should live in CMS placeholders/plugins only
- versioning work can target CMS page content without carrying a second section-level content path

## Safe Rollout Plan

### Phase 1: Design And Isolation

- confirm which content types must be versioned first
- limit scope to focus-area page content only
- do not attempt to version every CMS-related model at once

Recommended first target:

- standard CMS page content used by focus-area pages

Avoid in first pass:

- custom versioning for any separate section-level model
- content migrations that rewrite all existing focus-area content
- any command that recreates pages or resets CMS trees

### Phase 2: Package And Settings

- add the CMS versioning package
- register versioning only for the relevant CMS content type(s)
- update toolbar/admin integration as required by the package

Guardrail:

- this should be an additive install and migration, not a rebuild of the CMS database

### Phase 3: Existing Content Bootstrap

Existing live page content will need an initial "published" version baseline.

Safe approach:

1. back up the database first
2. run normal package migrations
3. bootstrap version records from existing live content
4. verify pages still render exactly as before
5. only then test draft creation as a limited editor

This is the most sensitive phase.

## Likely Cause Of The Prior "Database Reset" Problem

I do not see any committed code in this repo that intentionally resets the database as part of CMS versioning. Based on the current codebase, the earlier incident was most likely one of these:

1. Environment pointed at a different or fresh database
   - this project reads DB settings from JSON or env vars in `settings.py`
   - switching `APP_CONFIG`, `DB_DATABASE`, or host values could make the app look "reset" even if the original DB still existed

2. A destructive local recovery step was used during setup
   - examples: recreating the database, running `flush`, loading a fresh fixture, or dropping CMS tables

3. CMS content bootstrap/versioning was attempted against the wrong content assumptions
   - if versioning setup expected version rows that did not exist yet
   - or if test/demo setup commands recreated pages after install

4. Migrations were run against a database that did not contain the expected CMS data
   - this can look like "everything reset" when the schema is present but content is missing

5. A separate local development config was used accidentally
   - this repo supports multiple config sources:
     - `APP_CONFIG`
     - `portal.conf.dev.json`
     - `portal.conf.json`
     - `.env`

Most likely inference:

- the prior issue was more likely environment/database-target drift than a normal Django migration literally deleting content

## Risk Controls Before We Implement

Before enabling CMS versioning for real, we should do all of the following:

1. Record the exact active DB connection values in the running environment
2. Take a full database backup
3. Capture counts for key CMS tables before changes
4. Confirm focus-area pages and titles before migrations
5. Run package migrations in a non-production clone first
6. Verify post-migration page counts and content counts match pre-migration values
7. Test with one limited editor account and one reviewer account

Suggested pre/post checks:

- `cms_page`
- `cms_pagecontent`
- `cms_placeholder`
- `cms_cmsplugin`
- `auth_group`
- `cms_pagepermission`

## Implementation Guardrails

- no `flush`
- no dropping/recreating the database
- no deleting or recreating focus-area pages as part of versioning install
- no broad content rewrite during initial rollout
- no mixing versioning install with unrelated permission refactors

## Recommended Implementation Strategy

Recommended path:

1. install CMS versioning in a clone of the current database
2. migrate schema only
3. bootstrap version metadata for existing page content
4. validate that public rendering is unchanged
5. validate that page-specific editors can save drafts without publishing
6. keep focus-area content on the CMS page-content path only

## Open Questions

- Are any focus pages still carrying content outside CMS page content?
- Do we need any additional cleanup after retiring the legacy section model?
- Is there a staging or clone database available for a dry run before touching the main environment?

## Recommendation

Do not treat this as a simple permission fix anymore.

Treat it as a controlled CMS versioning rollout with:

- backup first
- environment verification first
- schema migration first
- version bootstrap second
- permission testing third

That should give us a much safer path than the previous attempt.
