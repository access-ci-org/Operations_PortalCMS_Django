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

### Step 1: Configure News Workflow

This creates groups and permissions for news item workflow (draft → review → publish).

```bash
uv run python manage.py setup_groups
```

**What this creates:**
- `System Status Authors` - Can create and edit
- `System Status Publishers` - Can create, edit, and publish
- `System Status Managers` - Can create, edit, delete, review, and publish
- `Integration News Authors` - Can create and edit
- `Integration News Publishers` - Can create, edit, and publish
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

---

## User Management

### Adding Users to Groups

1. Go to Django Admin: `/admin/`
2. Navigate to: **Authentication and Authorization → Groups**
3. Click on a group (e.g., `System Status Publishers`)
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

**For Managers/Reviewers:**
1. View items with "Pending Review" status
2. Review content
3. Click "Approve" or "Reject" with comments
4. If approved, item moves to "Approved" status

**For Publishers:**
1. View approved items (or items pending review)
2. Click "Publish" to make live
3. Item status changes to "Published"

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
   - `System Status Publishers` or `System Status Managers` for news
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
