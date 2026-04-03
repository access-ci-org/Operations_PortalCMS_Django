# Focus Area Page Workflow

## Overview

Focus area pages (STEP, Cybersecurity, Operational Support, Data Transfer and Networking) now use Django CMS's built-in draft/publish workflow with role-based permissions.

As of 2026-04-03, this workflow has been verified end-to-end on the clone-backed environment using `djangocms_versioning`:

- a page-specific editor created a new draft for STEP
- the UI showed a separate draft version and compare-to-published controls
- a reviewer/superuser published the draft successfully
- the clone database recorded a new `cms_pagecontent` row and a new published version

At this point, page versioning is proven in the clone environment. `djangocms_moderation` has not been enabled.

## User Roles

### Page-Specific Editors
- **Groups**: Focus_STEP_Editors, Focus_Cybersecurity_Editors, Focus_operationsSupport_Editors, Focus_Networking_dataTransfer_Editors
- **Can**: Edit their assigned focus area page through standard Django CMS page editing
- **Cannot**: Publish changes directly (must submit for review)

### General Focus Area Editors (Reviewers/Publishers)
- **Group**: Focus_area_editors
- **Can**: Edit AND publish any focus area page
- **Role**: Reviews and approves changes from page-specific editors

## Workflow Steps

### 1. Editor Makes Changes

**Page-specific editor (e.g., STEP editor):**
1. Log into Django CMS admin
2. Navigate to the STEP focus area page
3. Click "Edit" to enter edit mode
4. Make changes to page content or sections
5. Click "Save" - changes are saved as draft (not published)
6. Confirm the version menu shows a draft version separate from the current published version

> **Important**: Page-specific focus editors should use standard Django CMS page editing only. Legacy `FocusAreaSection` editing has been retired from the project.

### 2. Request Review

The editor notifies a general focus area editor that changes are ready for review. This can be done via:
- Email
- Slack message
- Team communication channel
- Or any agreed-upon process

> **Note**: Django CMS doesn't have a built-in "Submit for Review" button, but editors can add comments or notes in the page's "Notes" field to indicate review status.

### 3. Review and Publish

**General focus area editor (reviewer):**
1. Log into Django CMS admin
2. Navigate to the focus area page with pending changes
3. Click "Preview" to see the draft changes
4. Review the changes:
   - If changes need adjustment: Make edits directly or request revisions
   - If changes are good: Proceed to publish
5. Click "Publish" button to make changes live

The page is now published and visible to all users.

## Technical Implementation

### Permissions

**Django Model Permissions** (applied to groups):
- Page-specific editors: `view_page`, `add_page`, `change_page`, plus required CMS structure/plugin edit permissions
- General editors: `view_page`, `add_page`, `change_page`, `publish_page`

**Django CMS PagePermissions** (page-specific):
- Page-specific editors: `can_change=True`, `can_publish=False`, `can_view=False`
- General editors: `can_change=True`, `can_publish=True`, `can_view=False`

**Public Visibility**:
- Focus-area pages are intended to remain publicly viewable
- `CMS_PUBLIC_FOR = 'all'` is used so page permissions govern editing/publishing, not anonymous page visibility

### Setup Commands

Configuration is done via management commands:

```bash
# 1. Configure group permissions (Django model level)
uv run python manage.py setup_groups

# 2. Configure page-specific permissions (CMS PagePermission level)
uv run python manage.py setup_focus_area_page_permissions
```

### Versioning Requirement

This workflow now depends on `djangocms_versioning` being installed and migrated for the environment you are testing.

Without CMS versioning, page edit vs publish permissions alone are not enough to hold changes back from the public page.

For the clone-backed browser test path, the app was run with:

- clone app config file: `/soft/django-cms-01/conf/portalcms-clone.conf.json`
- clone database: `portalcms1_clone`
- clone gunicorn socket: `/soft/django-cms-01/run/portalcms-clone.socket`
- temporary public nginx repoint from `cms2.operations.access-ci.org` to the clone socket

### Testing

Run the workflow test to verify permissions:

```bash
uv run python tests/test_focus_area_page_workflow.py
```

For current operational browser testing details, see [CMS_VERSIONING_CLONE_CHECKLIST.md](./CMS_VERSIONING_CLONE_CHECKLIST.md).

## Benefits of Page-Level Workflow

1. **Quality Control**: Changes reviewed before going live
2. **Simple**: Uses Django CMS native draft/publish functionality
3. **Flexible**: Reviewers can edit or request changes
4. **Scalable**: Same workflow applies to all focus area pages
5. **No Custom Code**: Leverages Django CMS built-in capabilities

## Comparison with News Workflow

| Aspect | News Items | Focus Area Pages |
|--------|------------|------------------|
| Granularity | Individual news items | Entire page |
| Workflow | Custom status field | Django CMS draft/publish |
| Review | Explicit approve/reject buttons | Publish button |
| Comments | Review comments field | Page notes/annotations |
| Notifications | Could add custom | Via external communication |

## For Administrators

### Adding Users to Groups

1. Go to Django Admin: `/admin/`
2. Navigate to: **Authentication and Authorization → Groups**
3. Select the appropriate group (e.g., `Focus_STEP_Editors`)
4. In the "Users" section, add users to the group
5. Save

### Checking Permissions

To verify a user's permissions on a specific page:

```python
from django.contrib.auth.models import User
from cms.models import Page

user = User.objects.get(username='...')
page = Page.objects.get(id=...)

print(f"Can change: {page.has_change_permission(user)}")
print(f"Can publish: {page.has_publish_permission(user)}")
```

### Re-running Permission Setup

If you add new focus area pages or groups, re-run the setup commands:

```bash
uv run python manage.py setup_focus_area_page_permissions
```

This is safe to run multiple times - it will update existing permissions without duplicating them.

## Troubleshooting

### Editor Can't See Pages

**Problem**: User in Focus_STEP_Editors group can't see or edit STEP page

**Solutions**:
1. Ensure user has `is_staff = True` (required for CMS access)
2. Verify user is in the correct group
3. Re-run `setup_groups` and `setup_focus_area_page_permissions`
4. Confirm the user is editing through standard CMS page edit mode, not STEP block editing

### Can't Publish

**Problem**: User can't publish changes

**Expected**: Only Focus_area_editors group members should be able to publish

**If a publisher can't publish**:
1. Verify they're in the Focus_area_editors group
2. Run `setup_groups` to ensure they have `publish_page` permission
3. Run `setup_focus_area_page_permissions` to ensure PagePermissions are correct

### Logged-Out Users Get 404 On Focus Pages

**Problem**: Focus pages load for logged-in staff but 404 for anonymous users

**Expected**: Focus-area pages should remain publicly viewable

**Fixes**:
1. Ensure `CMS_PUBLIC_FOR = 'all'` in settings
2. Re-run `setup_focus_area_page_permissions`
3. Confirm focus-area `PagePermission` rows use `can_view=False`
4. Restart the CMS service

### Draft / Publish UI Is Missing

**Problem**: Editors can still edit pages, but version controls such as "New Draft" or compare-to-published are missing

**Checks**:
1. Verify `djangocms_versioning` is installed in the environment
2. Verify migrations have been applied
3. Confirm the environment is actually pointed at the intended database
4. If testing the clone path, verify nginx is pointing at the clone socket rather than the normal socket

### Legacy Section Changes Went Live Without Review

**Problem**: Legacy section content changed immediately after editing

**Cause**: The edit was made outside the normal Django CMS page draft workflow

**Fix**:
1. Use standard CMS page edit mode for page-specific editor workflow
2. Save draft as the page-specific editor
3. Verify the public page from a logged-out/incognito browser before reviewer publish
4. Do not reintroduce model-backed section editing as part of the focus-area workflow

## Related Documentation

- [CMS Page Permissions](./CMS_PAGE_PERMISSIONS.md) - Django CMS permission system details
- [Focus Area Block Permissions](./FOCUS_AREA_BLOCK_LEVEL.md) - Section-level editing permissions
- [News Permissions](./NEWS_PERMISSIONS.md) - News item workflow
