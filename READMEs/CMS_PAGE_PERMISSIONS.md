# CMS Page-Level Permissions Guide

## Overview

Django CMS supports page-level permissions, allowing you to restrict which users can **view** or **edit** specific pages based on their group membership.

**Use Cases:**
- **PIs managing public pages** - Grant edit access to principal investigators
- **Managers controlling focus areas** - Cybersecurity, Networking, Operational Support, STEP pages
- **Department-specific content** - Only certain teams should edit certain sections

**Note:** This guide covers **CMS page permissions**. For controlling who can add/edit **news items** (System Status and Integration News), see [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md).

Last checked against RDS `portal1`: 2026-04-24. See [CURRENT_STATE.md](./CURRENT_STATE.md) for the actual page-permission rows currently installed.

## Permission Strategy

### Resource Provider (RP) Groups → News Items Only
RP groups from CILogon are used to control **news items**, not CMS pages:
- ✅ Can add/edit System Status News
- ✅ Can add/edit Integration News  
- ❌ Not used for CMS page permissions

### Custom Groups → CMS Pages
Create custom Django groups for page management:
- "PI Editors" - Can edit public-facing pages
- "Cybersecurity Managers" - Can edit cybersecurity focus area
- "Networking Managers" - Can edit networking focus area
- "Operations Staff" - Can edit operations pages

## How It Works

### 1. Page Permissions Are Already Enabled

Your `settings.py` has:
```python
CMS_PERMISSION = True
```

This enables the page permission system.

### 2. Available Permission Types

For each CMS page, you can control:

- **View Restrictions** - Who can see the page on the public site
- **Edit Permissions** - Who can edit the page content
- **Add/Delete/Move** - Who can manage page structure
- **Moderator** - Who can publish/unpublish pages

## Setting Page Permissions in Admin

### Step 1: Access Page Permissions

1. Log into Django Admin: `/admin/`
2. Go to **Pages** (or use the CMS toolbar when viewing a page)
3. Select a page or create a new one
4. Click **Permissions** tab (or the lock icon)

### Step 2: Enable Page-Level Permissions

1. Check **"Can change permissions"** for the groups that should manage this page
2. Enable specific permissions for each group

### Step 3: Assign Groups to Pages

Create groups in Django Admin and assign them to pages:

**Example: Public Page Managed by PIs**
- **Can view**: Public (everyone)
- **Can edit**: Group: "PI Editors"
- **Can publish**: Group: "PI Editors"

**Example: Focus Area Page**
- **Can view**: Public (everyone)
- **Can edit**: Group: `Focus_Cybersecurity_Editors`
- **Can publish**: Group: `Focus_area_editors`

**Example: Internal Operations Page**
- **Can view**: Group: "Operations Staff"
- **Can edit**: Group: "Operations Staff"  
- **Can publish**: Group: "Operations Staff"

## Common Patterns

### Pattern 1: PI-Managed Public Pages

PIs can edit public-facing content pages:

```
/about/
  /team/          ← PI Editors can edit
  /publications/  ← PI Editors can edit
  /contacts/      ← PI Editors can edit
```

**Page Permissions:**
- View: Public (everyone)
- Edit: Group: "PI Editors"
- Publish: Group: "PI Editors"
- Change Permissions: Site admins only

### Pattern 2: Focus Area Pages

Each focus area has dedicated managers:

```
/focus-areas/
  /cybersecurity/       ← Focus_Cybersecurity_Editors edit; Focus_area_editors publish
  /networking/          ← Focus_Networking_dataTransfer_Editors edit; Focus_area_editors publish
  /operational-support/ ← Focus_operationsSupport_Editors edit; Focus_area_editors publish
  /step/                ← Focus_STEP_Editors edit; Focus_area_editors publish
```

**Page Permissions for `/focus-areas/cybersecurity/`:**
- View: Public
- Edit: Group: `Focus_Cybersecurity_Editors`
- Publish: Group: `Focus_area_editors`

### Pattern 3: Internal/Protected Pages

Pages visible only to specific staff:

```
/internal/
  /roadmap/       ← Only roadmap maintainers
  /planning/      ← Only operations staff
```

**Page Permissions for `/internal/roadmap/`:**
- View: Group: "Roadmap Maintainers"
- Edit: Group: "Roadmap Maintainers"
- Publish: Group: "Roadmap Maintainers"

## Via Django Admin UI

### Setting Permissions Through Admin

1. Navigate to `/admin/cms/page/`
2. Click on a page
3. Click **Permissions** tab
4. You'll see a matrix:

```
┌─────────────────────┬──────┬──────┬─────────┬─────────┐
│ Group               │ View │ Edit │ Publish │ Delete  │
├─────────────────────┼──────┼──────┼─────────┼─────────┤
│ PI Editors          │ ✓    │ ✓    │ ✓       │         │
│ Cybersecurity Mgrs  │ ✓    │ ✓    │ ✓       │         │
│ Operations Staff    │ ✓    │ ✓    │ ✓       │ ✓       │
└─────────────────────┴──────┴──────┴─────────┴─────────┘
```

5. Save the page

### Global Permissions vs Page Permissions

- **Global Permissions** - Set via User → Groups in admin
  - Control what users can do across the entire site
  
- **Page Permissions** - Set per page in CMS
  - Control who can view/edit specific pages
  - Overrides global permissions for that page

## Creating Custom Groups

### Via Django Admin

1. Go to `/admin/auth/group/`
2. Click "Add Group"
3. Enter group name (e.g., "PI Editors")
4. **Don't** assign Django permissions here (use CMS page permissions instead)
5. Save

### Assign Users to Groups

1. Go to `/admin/auth/user/`
2. Select a user
3. Scroll to "Groups" section
4. Move groups from "Available" to "Chosen"
5. Save

## Programmatically Setting Permissions

You can also set page permissions in code:

```python
from cms.models import ACCESS_PAGE_AND_DESCENDANTS, Page, PagePermission
from django.contrib.auth.models import Group

# Get the page by current title
page = next(page for page in Page.objects.all() if page.get_title('en', fallback=True) == 'CyberSecurity')

# Get or create the group
cyber_group, _ = Group.objects.get_or_create(name='Focus_Cybersecurity_Editors')

# Add edit permission
PagePermission.objects.create(
    page=page,
    group=cyber_group,
    grant_on=ACCESS_PAGE_AND_DESCENDANTS,
    can_view=False,
    can_change=True,
    can_add=True,
    can_delete=False,
    can_move_page=True,
    can_change_advanced_settings=False,
    can_publish=False,
    can_change_permissions=False,
)
```

## Example: Setup Focus Area Pages

Create pages with proper permissions for focus areas:

```python
# management/commands/setup_focus_areas.py
from django.core.management.base import BaseCommand
from cms.api import create_page
from cms.models import PagePermission
from django.contrib.auth.models import Group

class Command(BaseCommand):
    help = 'Create focus area pages with proper permissions'
    
    def handle(self, *args, **options):
        # Create parent page
        parent_page = create_page(
            title='Focus Areas',
            template='page.html',
            language='en',
            published=True,
        )
        
        focus_areas = [
            ('Cybersecurity', 'Cybersecurity Managers'),
            ('Networking', 'Networking Managers'),
            ('Operational Support', 'Operations Managers'),
            ('STEP', 'STEP Managers'),
        ]
        
        for title, group_name in focus_areas:
            # Create page
            page = create_page(
                title=title,
                template='focus_area.html',
                language='en',
                parent=parent_page,
                published=True,
            )
            
            # Get or create group
            group, _ = Group.objects.get_or_create(name=group_name)
            
            # Set permissions
            PagePermission.objects.create(
                page=page,
                group=group,
                can_view=True,
                can_change=True,
                can_publish=True,
                can_change_permissions=False,
            )
            
            self.stdout.write(
                self.style.SUCCESS(f'✓ Created {title} page')
            )
```

## Checking Permissions in Templates

You can check if a user can access a page:

```django
{% load cms_tags %}

{% if request.current_page.has_view_permission user %}
    <h1>{{ request.current_page.get_title }}</h1>
    {% placeholder "content" %}
{% else %}
    <p>You don't have permission to view this page.</p>
{% endif %}
```

## View Restrictions vs Edit Restrictions

**View Restrictions** (Public Site):
- Controls who can see the page when browsing the site
- Users without permission get a 403 Forbidden error
- Useful for internal pages, staff-only content

**Edit Restrictions** (CMS Toolbar):
- Controls who can edit content using the CMS toolbar
- Users without permission won't see edit buttons
- Useful for delegating content management to specific teams

## Example Workflow

### Scenario: Create Cybersecurity Focus Area Page

1. **Create the page** in CMS:
   - Title: "Cybersecurity"
   - URL: `/focus-areas/cybersecurity/`
   - Template: Focus Area Page

2. **Create the group** in Admin:
   - Go to `/admin/auth/group/add/`
   - Name: "Cybersecurity Managers"
   - Save

3. **Set page permissions** in Page → Permissions:
   - **View**: Public (everyone can see it)
   - **Can change page**: Group: "Cybersecurity Managers"
   - **Can publish**: Group: "Cybersecurity Managers"

4. **Assign users to group**:
   - Go to `/admin/auth/user/`
   - Select user
   - Add to "Cybersecurity Managers" group
   - Save

5. **User logs in**:
   - If they're in the group, they'll see edit buttons on the page
   - If not, they can view but not edit

## Benefits

✅ **Flexible** - Create any groups you need (PIs, managers, departments)
✅ **Secure** - Fine-grained control over who can edit what  
✅ **Simple** - Direct group assignment, no complex rules  
✅ **Auditable** - Django logs all permission changes  
✅ **Scalable** - Add new groups and pages as needed  

## Troubleshooting

**Problem: User can't see edit buttons**
- Check `/admin/auth/user/` → select user → Groups section
- Verify they're in the correct group
- Check page permissions in `/admin/cms/page/` → Permissions tab
- Ensure `CMS_PERMISSION = True` in settings

**Problem: Group not appearing in permission dropdown**
- Verify group exists at `/admin/auth/group/`
- Refresh the page permissions page
- Make sure you're on the Permissions tab, not Advanced Settings

**Problem: Permission changes not taking effect**
- Log out and log back in
- Clear browser cache
- Check Django logs for errors

## Permission Separation

This system uses two types of permissions:

| Permission Type | Controls | Used For |
|----------------|----------|----------|
| **CMS Page Permissions** | Who can edit CMS pages | PIs, focus area managers, department editors |
| **News Permissions** | Who can add/edit news items | RP groups (via [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)) |

**Keep them separate:**
- RP groups → Used for news items only
- Custom groups → Used for CMS pages

## Summary

**CMS page permissions allow flexible content delegation:**

1. 📄 Create custom groups ("PI Editors", "Cybersecurity Managers", etc.)
2. 👥 Assign users to groups in Django Admin
3. 🔒 Set page permissions for each group
4. ✏️ Users can edit pages based on their group membership

**For news items:** RP groups automatically grant access (see [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)).

This gives you powerful, automatic, RP-based content management delegation.
