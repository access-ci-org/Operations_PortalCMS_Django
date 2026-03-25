# Focus Area Page Workflow

## Overview

Focus area pages (STEP, Cybersecurity, Operational Support, Data Transfer and Networking) now use Django CMS's built-in draft/publish workflow with role-based permissions.

## User Roles

### Page-Specific Editors
- **Groups**: Focus_STEP_Editors, Focus_Cybersecurity_Editors, Focus_operationsSupport_Editors, Focus_Networking_dataTransfer_Editors
- **Can**: Edit their assigned focus area page and sections
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
- Page-specific editors: `view_page`, `add_page`, `change_page`
- General editors: `view_page`, `add_page`, `change_page`, `publish_page`

**Django CMS PagePermissions** (page-specific):
- Page-specific editors: `can_change=True`, `can_publish=False`
- General editors: `can_change=True`, `can_publish=True`

### Setup Commands

Configuration is done via management commands:

```bash
# 1. Configure group permissions (Django model level)
uv run python manage.py setup_groups

# 2. Configure page-specific permissions (CMS PagePermission level)
uv run python manage.py setup_focus_area_page_permissions
```

### Testing

Run the workflow test to verify permissions:

```bash
uv run python tests/test_focus_area_page_workflow.py
```

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
4. Check that Django CMS page permissions are enabled on the page

### Can't Publish

**Problem**: User can't publish changes

**Expected**: Only Focus_area_editors group members should be able to publish

**If a publisher can't publish**:
1. Verify they're in the Focus_area_editors group
2. Run `setup_groups` to ensure they have `publish_page` permission
3. Run `setup_focus_area_page_permissions` to ensure PagePermissions are correct

## Related Documentation

- [CMS Page Permissions](./CMS_PAGE_PERMISSIONS.md) - Django CMS permission system details
- [Focus Area Block Permissions](./FOCUS_AREA_BLOCK_LEVEL.md) - Section-level editing permissions
- [News Permissions](./NEWS_PERMISSIONS.md) - News item workflow
