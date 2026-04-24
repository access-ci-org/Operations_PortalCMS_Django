# RP Permissions System - Technical Overview

This document explains the technical details of how Resource Provider (RP) permissions work in the Operations Portal CMS.

Last checked against RDS `portal1`: 2026-04-24. See [CURRENT_STATE.md](./CURRENT_STATE.md) for the full verification snapshot.

## What RP Permissions Control

**✅ RP Groups Control:**
- Adding/editing **System Status News**
- Adding/editing **Integration News**
- Automatic sync from CILogon group memberships

**✅ News Workflow Groups Control:**
- Which users can publish news
- Which users can review/manage news
- Role-specific testing for author/publisher/manager workflows

**❌ RP Groups Do NOT Control:**
- CMS page editing (use custom groups instead - see [CMS_PAGE_PERMISSIONS.md](CMS_PAGE_PERMISSIONS.md))

**For day-to-day usage:** See [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)
**This document:** Technical implementation details

## Overview

The permission system integrates CILogon authentication with Django's permissions to provide automatic access control for news items based on Resource Provider group memberships from COmanage.

On top of that, the project also uses explicit Django groups for workflow roles:

- `System Status Authors`
- `System Status Managers`
- `Integration News Authors`
- `Integration News Managers`

These groups are created by:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_groups
```

## How It Works

### 1. CIDER Models

Four models sync data from the CIDER API:
- **CiderInfrastructure** - Compute resources, storage, cloud platforms
- **CiderOrganizations** - Sites, institutions, providers
- **CiderFeatures** - Resource capabilities and specifications  
- **CiderGroups** - Resource Provider groups (used for permissions)

### 2. Permission Creation

Run the management command to create permissions and groups:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_rp_permissions --dry-run
```

This creates:

**Per-RP Permissions:**
- For each RP in `CiderGroups`, creates permissions like:
  - `implementer_<groupid>` 
  - `coordinator_<groupid>`
- Creates Django groups matching CILogon URN format:
  - `urn:group:access-ci.org:<groupid>:implementer`
  - `urn:group:access-ci.org:<groupid>:coordinator`

**Global Operations Permissions:**
- `concierge` → `urn:group:access-ci.org:operations.access-ci.org:concierge`
- `badge.maintainer` → `urn:group:access-ci.org:operations.access-ci.org:badge.maintainer`
- `roadmap.maintainer` → `urn:group:access-ci.org:operations.access-ci.org:roadmap.maintainer`

Current caveat: the RDS `cider_groups` table contains 26 current CIDER API records, all currently `resource-catalog.access-ci.org` groups. The Django auth group table still contains the older five RP-style group pairs plus three operations URN groups. `setup_rp_permissions` is idempotent and supports `--dry-run`, but a real run writes auth groups and permissions for each selected `CiderGroups` row, so confirm the intended CIDER group scope before running it against the database of record.

### 3. Automatic Group Sync on Login

When a user logs in via CILogon:

1. **CILogon returns group memberships** in the `isMemberOf` claim as URNs:
   ```
   ['urn:group:access-ci.org:rp.access-ci.org:coordinator', ...]
   ```

2. **Signal handler syncs groups** (`signals.py:sync_cilogon_groups()`):
   - Extracts ACCESS-CI group URNs from CILogon claims
   - Matches them to Django groups created by `setup_rp_permissions`
   - Adds user to matching groups
   - Removes user from groups they no longer belong to

3. **User gets permissions** automatically through group membership

## Usage in Views

Check permissions in views:

```python
from django.contrib.auth.decorators import permission_required

@permission_required('operations_portalcms_django.coordinator_rp.access-ci.org')
def edit_rp_content(request):
    # Only RP coordinators can access
    pass
```

Check if user has any implementer role:
```python
def my_view(request):
    user_perms = request.user.get_all_permissions()
    is_implementer = any('implementer_' in p for p in user_perms)
```

Check group membership:
```python
def my_view(request):
    is_coordinator = request.user.groups.filter(
        name__contains=':coordinator'
    ).exists()
```

## Admin Interface

View and manage CIDER data in Django Admin:

- **CIDER Groups** - View RPs and their linked Django groups
- **CIDER Infrastructure** - Browse resources
- **CIDER Organizations** - View sites/institutions
- **CIDER Features** - View capabilities

## Testing the System

1. **Check database migrations and model drift:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py makemigrations --check --dry-run

   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py showmigrations operations_portalcms_django
   ```

2. **Check CIDER data freshness without writes:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py sync_cider_from_api --dry-run
   ```

3. **Preview permission/auth-group writes:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py setup_rp_permissions --dry-run --skip-global-operations
   ```

Use `--dry-run`, `--group-prefix`, `--group-type`, and `--skip-global-operations` to preview or narrow the auth group writes before a real run:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_rp_permissions --dry-run --skip-global-operations

APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_rp_permissions \
  --dry-run \
  --skip-global-operations \
  --group-type resource-catalog.access-ci.org
```

4. **Test login:**
   - Log in via CILogon
   - Check Django Admin → Users → [your user] → Groups
   - Should see RP groups automatically assigned

5. **Verify permissions:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py shell
   >>> from django.contrib.auth.models import User
   >>> user = User.objects.get(username='your_username')
   >>> user.groups.all()
   >>> user.get_all_permissions()
   ```

## Troubleshooting

### Groups not syncing on login

Check logs for CILogon group sync:
```bash
tail -f /soft/django-cms-01/var/portal.log | grep "CILogon groups"
```

### No permissions showing up

1. Verify groups were created:
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py shell
   >>> from django.contrib.auth.models import Group
   >>> Group.objects.filter(name__startswith='urn:group:access-ci.org:')
   ```

2. Re-run permission setup:
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py setup_rp_permissions --dry-run
   ```

### CILogon URNs don't match

The group names in Django must **exactly match** the URN format from CILogon's `isMemberOf` claim. Check:
- CILogon claim format in logs
- Django group names in admin
- Adjust `setup_rp_permissions.py` if needed

## Architecture Diagram

```
CILogon Login
     ↓
[isMemberOf claim with URNs]
     ↓
Signal: sync_cilogon_groups()
     ↓
Match URNs to Django Groups
     ↓
User.groups.add(matching_groups)
     ↓
Permissions via Group membership
     ↓
View decorators check permissions
```

## Current Boundaries

- RP groups are used for news-management access, not CMS page editing.
- Focus-area CMS page workflow uses separate `Focus_*` groups and `djangocms_versioning`.
- The current app already has view/admin permission checks for news management.
- RP-specific dashboards or RP-scoped CMS page editing would be new work, not part of the current verified state.
