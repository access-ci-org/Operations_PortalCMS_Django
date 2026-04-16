# Operations Portal CMS - Complete Setup Guide

This guide walks through the complete setup of all permission systems and workflows in the Operations Portal CMS.

## Overview

The portal uses three separate workflows:

1. **News Workflow** - Draft/review/publish for System Status and Integration News
2. **Focus Area Page Workflow** - Draft/publish for focus area pages using Django CMS
3. **RP Permissions** (Optional) - Automatic news access for Resource Provider coordinators

## Prerequisites

- Django CMS project installed and migrations run
- Superuser account created
- Development or production database configured

## Complete Setup Process

For clone-first focus-area versioning rollout notes, also see:

- [CMS_VERSIONING_CLONE_CHECKLIST.md](./CMS_VERSIONING_CLONE_CHECKLIST.md)
- [CMS_VERSIONING_ROLLOUT_PLAN.md](./CMS_VERSIONING_ROLLOUT_PLAN.md)

## Current Operational State

As of 2026-04-07:

- Canonical application database: `portal1`
- Canonical database host: `opsdb-dev.cluster-clabf5kcvwmz.us-east-2.rds.amazonaws.com`
- Canonical database owner: `portal_owner`
- Canonical application role/schema: `portal_django` / `portal_django`
- Canonical SSL mode: `require`
- Local pre-cutover source database retained for rollback: `portalcms1`
- Active app service: `portal.service`
- Active app socket: `/soft/django-cms-01/run/portal.socket`
- Public nginx vhost: `/etc/nginx/sites-available/nginx.portal`
- Current deployed runtime config: `/soft/django-cms-01/conf/portal.conf.dev.json`
- Future intended secret/config source: Ansible-managed `portal.conf` rendered from vaulted deployment variables
- Latest local pre-cutover backup: `/soft/django-cms-01/tags/Operations_PortalCMS_Django/backups/portalcms1_pre_rds_cutover_20260407T192613Z.dump`
- Live config rollback copy: `/soft/django-cms-01/conf/portal.conf.dev.pre_rds_cutover_20260407T192826Z.json`
- Current manual Django admin wrapper in the repo: `manage.prod.sh.j2`

### Step 1: Configure News Workflow

This creates groups and permissions for news item workflow (draft → review → publish).

```bash
uv run python manage.py setup_groups
```

**What this creates:**
- `System Status Authors` - Can create and edit; must submit for review to publish
- `System Status Managers` - Can create, edit, delete, review, and publish
- `Integration News Authors` - Can create and edit; must submit for review to publish
- `Integration News Managers` - Can create, edit, delete, review, and publish

**Next:** Assign users to these groups via Django Admin (`/admin/auth/group/`)

**Documentation:** [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)

---

### Step 2: Configure Focus Area Page Workflow

This configures page-level draft/publish workflow for focus area pages.

```bash
# Configure page-specific permissions
uv run python manage.py setup_focus_area_page_permissions
```

**What this creates:**
- Permissions for `Focus_area_editors` to publish any focus area page
- Permissions for page-specific groups (Focus_STEP_Editors, etc.) to edit but not publish

**Additional requirement:** The environment must also have `djangocms_versioning` installed and migrated for true draft/publish separation.

**Next:** Assign users to focus area editor groups via Django Admin

**Documentation:** [FOCUS_AREA_WORKFLOW.md](FOCUS_AREA_WORKFLOW.md)

---

### Step 3: Configure RP Permissions (Optional)

This is only needed if you want Resource Provider coordinators to automatically get news access based on CILogon groups.

```bash
# Create RP groups and permissions
uv run python manage.py setup_rp_permissions

# Load test CIDER data for development
uv run python manage.py load_test_cider_data
```

**What this creates:**
- RP groups synced from CIDER (e.g., `urn:group:access-ci.org:rp.psc.edu:coordinator`)
- Automatic news access for users in these groups via CILogon authentication

**For production:** Replace `load_test_cider_data` with:
```bash
uv run python manage.py sync_cider_from_api
```

**Documentation:** [QUICKSTART_PERMISSIONS.md](QUICKSTART_PERMISSIONS.md)

---

## Verification

### Test News Workflow

```bash
uv run python tests/test_news_permissions.py
```

Expected output:
```
✓ Helper functions working correctly
✓ Admin permissions correctly configured
✓ Workflow actions work as expected
✓ All tests passed
```

### Test Focus Area Workflow

```bash
uv run python tests/test_focus_area_page_workflow.py
```

Expected output:
```
✓ STEP editors can edit but NOT publish
✓ General focus area editors can edit AND publish
✓ Django CMS built-in workflow is properly configured
✓ All tests passed
```

### Historical Clone-Backed Versioning Workflow

Historical note:

- The clone-backed test path below was the rollout validation path.
- As of 2026-04-06, that validated database had already been promoted into the canonical local `portalcms1` name.
- As of 2026-04-07, the standard runtime has moved again and now points at RDS `portal1`.

The retired browser test path used:

- clone DB: `portalcms1_clone`
- clone app config: `/soft/django-cms-01/conf/portal-clone.conf.json`
- clone gunicorn service: `portal-clone.service`
- clone socket: `/soft/django-cms-01/run/portal-clone.socket`

During the 2026-04-03 validation session, the public dev nginx vhost for `cms2.operations.access-ci.org` was temporarily repointed from the normal socket to the clone socket for real browser testing.

That allowed a normal browser session to verify:

- STEP editor creates draft
- reviewer/superuser publishes draft
- clone DB records a new published version and a new `cms_pagecontent` row

That path is now historical reference material only. Current runtime verification should use the active `portal.service` and the deployed RDS-backed config.

---

## User Management

### Adding Users to Groups

1. Go to Django Admin: `/admin/`
2. Navigate to: **Authentication and Authorization → Groups**
3. Click on a group (e.g., `System Status Authors`)
4. Scroll to "Users" section
5. Move users from "Available users" to "Chosen users"
6. Click "Save"

### Making Users Staff

Users must be staff to access Django CMS:

1. Go to: **Authentication and Authorization → Users**
2. Click on a user
3. Check "Staff status"
4. Assign groups (if not already done)
5. Click "Save"

---

## Workflow Examples

### News Item Workflow

**For Authors:**
1. Create news item via web interface
2. Fill in content
3. Status defaults to "draft"
4. Click "Submit for Review" when ready

**For Managers:**
1. View items with "Pending Review" status
2. Review content
3. Publish directly, or reject with comments
4. If published, item status changes to "Published"

**For Authors:**
1. View approved items are now published
2. No direct publish action available; submit for review instead

### Focus Area Page Workflow

**For Page-Specific Editors (e.g., STEP editor):**
1. Log into Django CMS
2. Navigate to STEP page
3. Click "Edit" mode
4. Make changes to page content or sections
5. Click "Save" (saves as draft)
6. Notify general editor that changes are ready

**For General Focus Area Editors:**
1. Log into Django CMS
2. Navigate to page with draft changes
3. Click "Preview" to review changes
4. Click "Publish" to make live

Validated clone result:

- old published version remains intact until reviewer publish
- new `cms_pagecontent` row is created for the edited version
- prior live version becomes `unpublished` after the newer version is published

---

## Troubleshooting

### User Can't Access CMS

**Problem:** User logs in but doesn't see CMS pages

**Solutions:**
1. Ensure user has `is_staff = True`
2. Assign them to an appropriate group
3. Verify groups have necessary permissions

### User Can't Publish

**Problem:** User can edit but not publish

**Expected for:**
- News Authors (can't publish news)
- Page-specific focus area editors (can't publish pages)

**If a publisher can't publish:**
1. Verify they're in the correct group:
   - `System Status Managers` for news publishing/review
   - `Focus_area_editors` for focus area pages
2. Re-run setup commands:
   ```bash
   uv run python manage.py setup_groups
   uv run python manage.py setup_focus_area_page_permissions
   ```

### Permissions Changed, Now What?

If you modify permission structure, re-run the setup commands:

```bash
# All setup commands are idempotent and safe to re-run
uv run python manage.py setup_groups
uv run python manage.py setup_focus_area_page_permissions
```

This will update existing permissions without breaking anything.

---

## Maintenance

### Periodic Tasks

**Daily/Weekly:**
- Monitor news workflow (items stuck in review)
- Check for unpublished focus area changes

**Monthly:**
- Sync CIDER data (production):
  ```bash
  uv run python manage.py sync_cider_from_api
  ```
- Review group memberships
- Clean up inactive users

**After System Updates:**
- Re-run setup commands to ensure permissions are current:
  ```bash
  uv run python manage.py setup_groups
  uv run python manage.py setup_focus_area_page_permissions
  ```

---

## Command Reference

### Setup Commands

| Command | Purpose | Safe to Re-run |
|---------|---------|----------------|
| `setup_groups` | Configure news and focus area groups | ✅ Yes |
| `setup_focus_area_page_permissions` | Configure page-specific permissions | ✅ Yes |
| `setup_rp_permissions` | Configure RP groups and permissions | ✅ Yes |
| `load_test_cider_data` | Load test CIDER data (dev only) | ✅ Yes |
| `sync_cider_from_api` | Sync live CIDER data (production) | ✅ Yes |

### Legacy Migration Commands

| Command | Purpose |
|---------|---------|
| `setup_groups --migrate-legacy-memberships` | Migrate users from old groups |
| `setup_groups --delete-legacy-groups` | Delete old groups after migration |

### Test Commands

| Command | Purpose |
|---------|---------|
| `uv run python tests/test_news_permissions.py` | Test news workflow |
| `uv run python tests/test_focus_area_page_workflow.py` | Test focus area workflow |

---

## Quick Reference

### I want to...

**Configure news workflow:**
```bash
uv run python manage.py setup_groups
```
Then assign users to Author/Publisher/Manager groups.

**Configure focus area workflow:**
```bash
uv run python manage.py setup_groups
uv run python manage.py setup_focus_area_page_permissions
```
Then assign users to focus area editor groups.

**Give a user news editing permission:**
1. Ensure they're staff
2. Add them to appropriate news group

**Give a user focus area editing permission:**
1. Ensure they're staff  
2. Add them to `Focus_area_editors` (can publish) or specific page group (can only edit)

**Reset all permissions:**
```bash
uv run python manage.py setup_groups
uv run python manage.py setup_focus_area_page_permissions
```

---

## Documentation

**Workflow Guides:**
- [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md) - News workflow details
- [FOCUS_AREA_WORKFLOW.md](FOCUS_AREA_WORKFLOW.md) - Focus area workflow details
- [PERMISSIONS_SUMMARY.md](PERMISSIONS_SUMMARY.md) - High-level overview

**Technical Details:**
- [PERMISSIONS.md](PERMISSIONS.md) - Implementation details
- [CMS_PAGE_PERMISSIONS.md](CMS_PAGE_PERMISSIONS.md) - CMS page permissions
- [QUICKSTART_PERMISSIONS.md](QUICKSTART_PERMISSIONS.md) - RP permissions

---

## Support

For issues or questions:

1. Check this documentation
2. Run test commands to verify configuration
3. Check Django logs for errors
4. Review user group memberships in Django Admin

All setup commands can be safely re-run to fix configuration issues.
