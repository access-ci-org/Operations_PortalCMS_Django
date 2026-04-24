# Workflow Testing Guide

This guide covers testing procedures for all workflow implementations in the Portal CMS, including both automated and manual testing scenarios.

Current environment note:

- As of 2026-04-07, the standard runtime uses Amazon RDS database `portal1`.
- The historical clone-backed browser path below is retained only as rollout history.
- Last checked against RDS `portal1`: 2026-04-24. See [CURRENT_STATE.md](./CURRENT_STATE.md) for the read-only verification snapshot.

## Quick Start Testing

### Run All Automated Tests

These scripts mutate the configured database. Use a disposable clone or explicit non-production config.

```bash
# Test Focus Area page workflow
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_focus_area_page_workflow.py

# Test News permissions
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_news_permissions.py

# Test all permissions
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_permissions.py
```

---

## Focus Area Page Workflow Testing

### Overview
Focus Area pages use Django CMS's built-in draft/publish workflow with a two-tier permission model:
- **Page-Specific Editors**: Can edit their assigned pages but cannot publish
- **General Editors/Reviewers**: Can edit and publish all focus area pages

### Implementation Details
- **Approach**: Page-level workflow using Django CMS native features (NOT section-level)
- **Key Decision**: No custom workflow fields on models; leverage built-in CMS capabilities
- **Permissions**: Combination of PagePermission objects + Django model-level permissions
- **Grant Type**: ACCESS_PAGE_AND_DESCENDANTS (affects page and all child pages)
- **Public Visibility**: Focus-area pages remain publicly viewable; editor groups control editing/publishing only

### Known Good STEP Workflow

This is the currently validated model for the STEP page:

- Public users can view `/focus-areas/step/` without logging in
- `Focus_STEP_Editors` can edit STEP through standard Django CMS page editing
- `Focus_STEP_Editors` can save draft changes
- `Focus_STEP_Editors` can use `Submit for Review` to release their draft lock
- `Focus_STEP_Editors` cannot publish STEP directly
- `Focus_area_editors` can review and publish STEP
- `Focus_area_editors` can unlock a draft if handoff needs manual recovery
- django CMS versioning creates a separate draft version before publish
- publishing creates a new current `cms_pagecontent` row rather than editing the old live row in place

For a clean STEP editor test user:

- `is_staff = True`
- `is_superuser = False`
- member of `Focus_STEP_Editors` only
- no direct user permissions
- no direct `cms_pagepermission`
- no direct `cms_globalpagepermission`

### Important Constraint: Use CMS Page Editing Only

Focus-area workflow is now intended to use page-level CMS workflow only.

Do not test focus-area review workflow through any legacy section-editing path. Focus-area pages now rely on CMS placeholders/plugins only.

For focus-area workflow testing, always use the standard Django CMS page edit path:

1. Open STEP in Django CMS page edit mode
2. Edit normal CMS placeholder/plugin content
3. Save draft
4. Use `Submit for Review` to release the draft lock
5. Verify that publish is not available to `Focus_STEP_Editors`
6. Publish only as a `Focus_area_editors` reviewer

### Automated Testing
```bash
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_focus_area_page_workflow.py
```

**Test Coverage**:
- Page-specific editors can change their pages but not publish
- General editors can change and publish all focus area pages
- Permission isolation (STEP editors can't access Cybersecurity pages, etc.)

### Manual Testing Checklist

#### Test 1: Page-Specific Editor (Edit Only)
**User Role**: Focus_STEP_Editors group member

1. Log in to Django CMS admin
2. Navigate to Pages → Focus Areas → STEP
3. Click "Edit" to enter draft mode
4. Make content changes (add text, edit sections)
5. **Expected**: Changes save successfully
6. Look for "Publish" button
7. **Expected**: "Publish" button should be disabled or missing
8. Click "Save and close"
9. **Expected**: Page remains in draft state, unpublished
10. Open STEP in a logged-out/incognito browser window
11. **Expected**: Public page should still show the old content until a reviewer publishes
12. **Expected**: The version UI should show a new draft version, not overwrite the published version directly
13. Click **Submit for Review**
14. **Expected**: Draft remains unpublished but becomes available for a reviewer to take over

#### Test 2: General Editor (Edit + Publish)
**User Role**: Focus_area_editors group member

1. Log in to Django CMS admin
2. Navigate to Pages → Focus Areas
3. View pages with pending changes (indicated by draft indicator)
4. Click "Edit" on any focus area page (STEP, Cybersecurity, etc.)
5. Review the pending changes
6. Make additional edits if needed
7. **Expected**: All changes save successfully
8. Click "Publish"
9. **Expected**: Page publishes successfully and is now live

If the draft was not submitted cleanly, use **Unlock** first and then continue review.

#### Test 3: Permission Isolation
**User Roles**: Focus_STEP_Editors, Focus_Cybersecurity_Editors

1. Log in as STEP editor
2. Navigate to Pages → Focus Areas
3. **Expected**: Can only see/edit STEP pages
4. Try to access Cybersecurity page directly (via URL or search)
5. **Expected**: Access denied or page not visible

6. Log out and log in as Cybersecurity editor
7. Navigate to Pages → Focus Areas
8. **Expected**: Can only see/edit Cybersecurity pages
9. Try to access STEP page
10. **Expected**: Access denied or page not visible

#### Test 4: Review Workflow
**Simulates full workflow cycle**

1. **As STEP Editor**:
   - Make significant content changes to STEP page using standard CMS page edit mode
   - Add note: "Ready for review - updated contact information"
   - Save and click `Submit for Review` (do not publish)

2. **As General Editor (Reviewer)**:
   - View draft changes in CMS
   - Review content for accuracy
   - Verify formatting and links
   - **Decision**: Approve or request changes

3. **If Approved**:
   - Click "Publish"
   - Verify live site shows updated content
   - Check publish date/history
   - Confirm the old live version is no longer current

4. **If Changes Needed**:
   - Add review comments
   - Contact STEP editor
   - STEP editor makes revisions
   - Repeat cycle

#### Test 5: Public Visibility
**Confirms that page permissions do not hide the public page**

1. Open `/focus-areas/step/` in a logged-out browser
2. **Expected**: STEP page loads successfully
3. Open `/focus-areas/cybersecurity/` in a logged-out browser
4. **Expected**: Cybersecurity page loads successfully
5. Log in as `jlambertson`
6. Open STEP in CMS edit mode and save a draft-only change
7. Recheck `/focus-areas/step/` in a logged-out/incognito browser
8. **Expected**: Public page still shows the previously published content

#### Test 6: Historical Clone-Backed Public Browser Path

This was the browser-based test path used on the server during clone validation:

Historical note:

- This section describes the short-lived clone-backed validation path.
- As of 2026-04-06, that validated database has been promoted into the standard `portalcms1` name and the canonical public runtime is back on `portal.service` and `portal.socket`.
- As of 2026-04-07, the active runtime has moved again and now points at RDS `portal1` through `/soft/django-cms-01/conf/portal.conf.dev.json`.
- The clone-specific service, socket, and config file below are historical references, not current runtime dependencies.

- public URL: `https://cms2.operations.access-ci.org/`
- clone DB: `portalcms1_clone`
- clone config file: `/soft/django-cms-01/conf/portal-clone.conf.json`
- clone service: `portal-clone.service`
- clone socket: `/soft/django-cms-01/run/portal-clone.socket`

Important:

- the normal public dev hostname was temporarily repointed to the clone socket for browser testing
- this is suitable for short-lived testing when the server is mostly being used by one person
- switch the vhost back when clone testing is complete
- this path is no longer the standard validation path

---

## News Workflow Testing

### Overview
System Status News and Integration News use custom workflow states:
- `draft` → `pending_review` → `approved` → `published`

### Automated Testing
```bash
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_news_permissions.py
```

### Manual Testing
See [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md) for detailed news workflow testing procedures.

---

## Troubleshooting

### Page-Specific Editor Can't Edit
**Problem**: User in Focus_STEP_Editors can't edit STEP page

**Checks**:
1. Verify user is in correct group: Admin → Users → [username] → Groups
2. Check PagePermission exists: Admin → User and Group Permissions → Pages
3. Verify permission has `can_change=True` for the group
4. Check page assignment: Does PagePermission target correct page?
5. Run setup command: `python manage.py setup_focus_area_page_permissions`

### General Editor Can't Publish
**Problem**: User in Focus_area_editors can't publish pages

**Checks**:
1. Verify group has model-level permission: `cms.publish_page`
2. Check PagePermission has `can_publish=True` for Focus_area_editors
3. Verify user is in Focus_area_editors group
4. Run setup command: `python manage.py setup_groups`
5. Check for conflicting page-specific restrictions

### Permission Setup Not Working
**Problem**: Setup commands run but permissions don't work

**Solution**:
```bash
# 1. Re-run both setup commands in order
python manage.py setup_groups
python manage.py setup_focus_area_page_permissions

# 2. Check database for permission objects
python manage.py shell
>>> from cms.models import PagePermission
>>> PagePermission.objects.filter(group__name__contains='Focus').count()
# Should return multiple permissions

# 3. Verify group permissions
>>> from django.contrib.auth.models import Group, Permission
>>> focus_group = Group.objects.get(name='Focus_area_editors')
>>> focus_group.permissions.filter(codename__in=['change_page', 'publish_page']).count()
# Should return 2

# 4. Clear user sessions (force re-login)
>>> from django.contrib.sessions.models import Session
>>> Session.objects.all().delete()
```

### Focus Pages 404 For Logged-Out Users
**Problem**: Focus-area pages work when logged in, but return 404 when logged out

**Cause**:
- Django CMS page permissions are enabled
- editor groups have page permissions
- public viewing was accidentally being treated as permission-restricted

**Fix**:
1. Ensure `CMS_PUBLIC_FOR = 'all'` in settings
2. Re-run `python manage.py setup_focus_area_page_permissions`
3. Confirm focus-area `PagePermission` rows use `can_view=False`
4. Restart the CMS service

**Expected Result**:
- anonymous users can view focus-area pages
- editor groups can still edit
- only `Focus_area_editors` can publish

### Focus Editor Change Went Live Immediately
**Problem**: A focus-area content change appeared live immediately without review

**Cause**:
- edit was made outside the intended CMS draft/publish path

**Fix**:
1. Use standard Django CMS page edit mode only for page-specific editor testing
2. Treat CMS placeholders/plugins as the only supported focus-area content path
3. Save as draft and verify from a logged-out browser before reviewer publish

### Historical Clone Browser Test Is Still Hitting Live DB

**Problem**: Clone testing changes do not appear to match the clone DB state

**Checks**:
1. Verify the public nginx vhost upstream is pointing at `/soft/django-cms-01/run/portal-clone.socket`
2. Verify `portal-clone.service` is running
3. Verify clone config file points at `portalcms1_clone`
4. If needed, run a direct DB check before and after page edits to confirm which DB is changing

### Test Failures
**Problem**: Automated tests fail

**Debug Steps**:
```bash
# Run with verbose output
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_focus_area_page_workflow.py

# Check selected database/config first
APP_CONFIG=/path/to/non-production-config.json uv run python manage.py check

# Review test output for specific assertion failures
# Common issues:
# - Missing PagePermission objects (test setup incomplete)
# - Missing model permissions (setup_groups not called in test)
# - Wrong page hierarchy (parent/child relationships)
```

---

## Setup Commands Reference

### Initialize Groups and Permissions
```bash
# Creates groups and assigns base CMS permissions
python manage.py setup_groups
```

**What it does**:
- Creates Focus_area_editors, Focus_STEP_Editors, etc.
- Grants CMS page edit permissions needed for standard page editing, including structure/plugin editing
- Grants publish_page ONLY to Focus_area_editors (reviewers)
- Configures news workflow groups (System_Status_editors, etc.)

### Configure Page-Specific Permissions
```bash
# Creates PagePermission objects for focus area pages
python manage.py setup_focus_area_page_permissions
```

**What it does**:
- Finds all focus area pages (STEP, Cybersecurity, etc.)
- Creates two PagePermission sets per page:
  - General editors: can_change=True, can_publish=True, can_view=False
  - Page-specific editors: can_change=True, can_publish=False, can_view=False
- Sets grant_on=ACCESS_PAGE_AND_DESCENDANTS
- Removes malformed mixed user/group page-permission rows if found

### Verify Setup
```bash
# Check database state
python manage.py shell
>>> from cms.models import PagePermission
>>> from django.contrib.auth.models import Group

# List all focus area permissions
>>> for perm in PagePermission.objects.filter(group__name__contains='Focus'):
...     print(f"{perm.page.get_title()} - {perm.group.name} - publish:{perm.can_publish}")

# Verify group permissions
>>> for group in Group.objects.filter(name__contains='Focus'):
...     perms = group.permissions.values_list('codename', flat=True)
...     print(f"{group.name}: {list(perms)}")
```

---

## Key Files Reference

### Setup Commands
- `operations_portalcms_django/management/commands/setup_groups.py`
- `operations_portalcms_django/management/commands/setup_focus_area_page_permissions.py`

### Tests
- `tests/test_focus_area_page_workflow.py` - Focus area page workflow
- `tests/test_news_permissions.py` - News workflow
- `tests/test_permissions.py` - General permissions

### Models
- `operations_portalcms_django/models.py` - news models and plugin models
- Note: focus-area content is now CMS-placeholder-only

### Documentation
- `READMEs/FOCUS_AREA_WORKFLOW.md` - Detailed focus area workflow guide
- `READMEs/WORKFLOW_TESTING.md` - Current known-good testing and troubleshooting notes
- `READMEs/NEWS_PERMISSIONS.md` - News workflow documentation
- `READMEs/SETUP_GUIDE.md` - Comprehensive setup instructions
- `READMEs/PERMISSIONS_SUMMARY.md` - Overview of all permissions

---

## Groups Overview

### Focus Area Groups
| Group Name | Pages | Can Edit | Can Publish | Role |
|------------|-------|----------|-------------|------|
| Focus_area_editors | All focus areas | ✅ | ✅ | Reviewer |
| Focus_STEP_Editors | STEP only | ✅ | ❌ | Editor |
| Focus_Cybersecurity_Editors | Cybersecurity only | ✅ | ❌ | Editor |
| Focus_Facilities_Editors | Facilities only | ✅ | ❌ | Editor |
| Focus_DesktopSupport_Editors | Desktop Support only | ✅ | ❌ | Editor |

### News Groups
See [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md) for news group details.

---

## Testing Frequency

### Daily (Development)
- Run automated tests before committing changes
- Spot-check manual workflows after permission changes

### Weekly (Staging)
- Complete manual testing checklist
- Verify all group permissions
- Test full workflow cycles

### Pre-Release (Production)
- Run all automated tests
- Complete full manual testing checklist for all workflows
- Verify with actual user accounts (not superusers)
- Document any issues or edge cases discovered

---

## Common Issues and Solutions

### "I don't see the Publish button"
- **Cause**: User lacks publish_page permission or PagePermission has can_publish=False
- **Solution**: Add user to Focus_area_editors group OR run setup_focus_area_page_permissions

### "Changes don't appear on live site"
- **Cause**: Page still in draft, not published
- **Solution**: User with publish permission must click "Publish" in CMS

### "Can't access any focus area pages"
- **Cause**: User not in any focus area group
- **Solution**: Add user to at least one Focus_*_Editors group

### "Tests pass but manual testing fails"
- **Cause**: Test environment differs from dev/production
- **Solution**: Re-run setup commands on target environment, clear sessions

---

## Additional Resources

- Django CMS Documentation: https://docs.django-cms.org/
- PagePermission API: Django CMS permissions reference
- Django Groups/Permissions: https://docs.djangoproject.com/en/5.2/topics/auth/

---

**Last Updated**: March 25, 2026
**Implementation Status**: Complete and tested
