# RP Permissions - Quick Start Guide

## What You Have

A working **Resource Provider (RP) permission system** that automatically grants access to **add/edit news items** based on CILogon group memberships from COmanage.

Last checked against RDS `portal1`: 2026-04-24. See [CURRENT_STATE.md](./CURRENT_STATE.md) for the full verification snapshot.

**What RP Groups Control:**
- ✅ Adding/editing System Status News
- ✅ Adding/editing Integration News  
- ✅ Automatic sync from CILogon

**What RP Groups Do NOT Control:**
- ❌ CMS page editing (use custom groups - see [CMS_PAGE_PERMISSIONS.md](CMS_PAGE_PERMISSIONS.md))

## What Was Created

### 1. Database Tables
- `cider_infrastructure` - Infrastructure resources (compute, storage, etc.)
- `cider_organizations` - Sites and institutions  
- `cider_features` - Resource capabilities
- `cider_groups` - Resource Provider groups

### 2. Current Django Groups

The live database currently has 23 Django groups total.

**Current per-RP groups (10):**
- `urn:group:access-ci.org:rp.psc.edu:coordinator`
- `urn:group:access-ci.org:rp.psc.edu:implementer`
- `urn:group:access-ci.org:rp.tacc.utexas.edu:coordinator`
- `urn:group:access-ci.org:rp.tacc.utexas.edu:implementer`
- paired coordinator/implementer groups also exist for SDSC, NCSA, and ACCESS

**Global Operations Groups (3):**
- `urn:group:access-ci.org:operations.access-ci.org:concierge`
- `urn:group:access-ci.org:operations.access-ci.org:badge.maintainer`
- `urn:group:access-ci.org:operations.access-ci.org:roadmap.maintainer`

**Workflow/CMS groups also present:**
- `System Status Authors`
- `System Status Managers`
- `Integration News Authors`
- `Integration News Managers`
- `Focus_area_editors`
- page-specific focus groups
- `Home_page_editors`

Important: the current `cider_groups` table contains 26 current CIDER API records, all currently `resource-catalog.access-ci.org` groups. Decide deliberately before running `setup_rp_permissions` against all current CIDER groups, because it writes Django auth groups and permissions. Preview first with `--dry-run`.

### 3. Permission Logic
Simple rule: **If you're in ANY RP group, you can add/edit news**
- No infrastructure matching required
- Encourages cross-RP collaboration
- See [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md) for details

## How It Works

```
┌─────────────────┐
│ User Logs In    │
│ via CILogon     │
└────────┬────────┘
         │
         ▼
┌─────────────────────────────────────────┐
│ CILogon Returns isMemberOf Claim:      │
│  - urn:group:access-ci.org:rp.psc.edu: │
│    coordinator                          │
└────────┬────────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ Signal Handler: sync_cilogon_groups()  │
│  - Matches URNs to Django groups       │
│  - Adds user to matching groups        │
└────────┬───────────────────────────────┘
         │
         ▼
┌────────────────────────────────────────┐
│ User Can Now Add/Edit News!            │
│  ✓ System Status News                  │
│  ✓ Integration News                    │
└────────────────────────────────────────┘
```

## Data Source: CIDER API

The CIDER (Cyber Infrastructure Description Repository) data comes from the **Operations API Warehouse**:
- API: `https://operations-api.access-ci.org/wh2/cider/`
- Provides authoritative RP groups, organizations, infrastructure

**Development:** Use test data
```bash
uv run python manage.py load_test_cider_data
```

**Production/RDS dry-run:** Sync from live API without writes
```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api --dry-run
```

**Production/RDS write:** Sync from live API
```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py sync_cider_from_api
```

## Current Setup Commands

```bash
# 1. Check model migration drift
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py makemigrations --check --dry-run

# 2. Check applied migrations
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py showmigrations operations_portalcms_django

# 3. Create/update RP permissions and groups only after confirming the CIDER group scope
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_rp_permissions --dry-run
```

## News Workflow Groups

Run this command to create the role-based news groups:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_groups
```

This creates:

- `System Status Authors`
- `System Status Managers`
- `Integration News Authors`
- `Integration News Managers`

Use these when you want to test the draft, submit-for-review, and publish flows separately.

### Legacy Group Migration

If older editor groups already exist, you can migrate users into the new manager groups:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_groups --migrate-legacy-memberships
```

After testing, you can delete the old groups:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_groups --delete-legacy-groups
```

## Next Steps

### In Production

1. **Replace test data with real CIDER API sync:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py sync_cider_from_api --dry-run
   ```

2. **Re-run permission setup when new RPs are added:**
   ```bash
   APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
   uv run python manage.py setup_rp_permissions --dry-run
   ```

3. **Monitor group sync in logs:**
   ```bash
   tail -f /soft/django-cms-01/var/portal.log | grep "CILogon groups"
   ```

### Using Permissions in Code

**In views:**
```python
from django.contrib.auth.decorators import permission_required

@permission_required('operations_portalcms_django.coordinator_rp.psc.edu')
def edit_psc_content(request):
    # Only PSC coordinators can access
    return render(request, 'edit.html')
```

**In templates:**
```django
{% if perms.operations_portalcms_django.coordinator_rp.psc.edu %}
    <a href="{% url 'edit_psc' %}">Edit PSC Content</a>
{% endif %}
```

**Check if user has ANY coordinator role:**
```python
def has_coordinator_role(user):
    return any(
        perm.endswith('coordinator')
        for perm in user.get_all_permissions()
    )
```

**Filter resources by user's RP:**
```python
def get_user_rps(user):
    """Get list of RPs the user belongs to"""
    rp_groups = user.groups.filter(
        name__startswith='urn:group:access-ci.org:rp.'
    )
    return [g.name.split(':')[3] for g in rp_groups]
```

## Viewing in Admin

Visit `/admin/` and check:
- **Auth → Groups** - See all RP groups
- **Auth → Users** - Select a user, scroll to "Groups" to see their RP roles
- **CIDER Groups** - See which Django groups are linked to each RP
- **CIDER Infrastructure** - Browse resources

## Testing

Run the test suite anytime:
```bash
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_permissions.py
```

Do not run the test scripts against RDS `portal1` unless you intend to create/modify test users and groups there. See [tests/README.md](../tests/README.md).

## Troubleshooting

**Problem: Users not getting groups on login**
- Check CILogon configuration in `settings.py`
- View logs: `tail -f /soft/django-cms-01/var/portal.log | grep CILogon`
- Verify CILogon is returning `isMemberOf` claim

**Problem: Permission checks fail**
- Format: `app_label.permission_codename`
- Example: `operations_portalcms_django.coordinator_rp.psc.edu`
- Check: `user.get_all_permissions()` in Django shell

**Problem: Groups don't match**
- Django group names MUST exactly match CILogon URN format
- Check admin: `/admin/auth/group/`
- Adjust `setup_rp_permissions.py` if needed

## Files Modified/Created

**Models:**
- `operations_portalcms_django/models.py` - Added CIDER models

**Signals:**
- `operations_portalcms_django/signals.py` - Added `sync_cilogon_groups()`

**Admin:**
- `operations_portalcms_django/admin.py` - Added CIDER admin interfaces

**Management Commands:**
- `management/commands/setup_rp_permissions.py` - Create permissions/groups
- `management/commands/load_test_cider_data.py` - Load test data

**Documentation:**
- `PERMISSIONS.md` - Detailed permission system documentation
- `QUICKSTART_PERMISSIONS.md` - This file

**Testing:**
- `test_permissions.py` - Permission system test suite

---

**Status:** ✓ Fully functional and tested
**Date:** March 10, 2026
