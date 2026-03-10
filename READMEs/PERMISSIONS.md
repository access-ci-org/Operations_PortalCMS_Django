# RP Permissions System - Technical Overview

This document explains the technical details of how Resource Provider (RP) permissions work in the Operations Portal CMS.

## What RP Permissions Control

**✅ RP Groups Control:**
- Adding/editing **System Status News**
- Adding/editing **Integration News**
- Automatic sync from CILogon group memberships

**❌ RP Groups Do NOT Control:**
- CMS page editing (use custom groups instead - see [CMS_PAGE_PERMISSIONS.md](CMS_PAGE_PERMISSIONS.md))

**For day-to-day usage:** See [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)
**This document:** Technical implementation details

## Overview

The permission system integrates CILogon authentication with Django's permissions to provide automatic access control for news items based on Resource Provider group memberships from COmanage.

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
python manage.py setup_rp_permissions
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

1. **Create database migrations:**
   ```bash
   python manage.py makemigrations
   python manage.py migrate
   ```

2. **Load CIDER data** (from API or fixtures):
   ```bash
   python manage.py load_cider_data
   ```

3. **Create permissions:**
   ```bash
   python manage.py setup_rp_permissions
   ```

4. **Test login:**
   - Log in via CILogon
   - Check Django Admin → Users → [your user] → Groups
   - Should see RP groups automatically assigned

5. **Verify permissions:**
   ```bash
   python manage.py shell
   >>> from django.contrib.auth.models import User
   >>> user = User.objects.get(username='your_username')
   >>> user.groups.all()
   >>> user.get_all_permissions()
   ```

## Troubleshooting

### Groups not syncing on login

Check logs for CILogon group sync:
```bash
tail -f var/portalcms.log | grep "CILogon groups"
```

### No permissions showing up

1. Verify groups were created:
   ```bash
   python manage.py shell
   >>> from django.contrib.auth.models import Group
   >>> Group.objects.filter(name__startswith='urn:group:access-ci.org:')
   ```

2. Re-run permission setup:
   ```bash
   python manage.py setup_rp_permissions
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

## Next Steps

- Implement view-level permission checks
- Create permission-based menu items
- Add RP-specific dashboards
- Restrict CMS page editing by RP
