# CIDER Data Integration

## Overview

This Django CMS uses **CIDER** (Cyber Infrastructure Description Repository) data to enable Resource Provider permissions. CIDER data lives in the **Operations API Warehouse** and is synced to this app's database.

## Architecture

```
┌─────────────────────────────────────────────┐
│   CIDER System (Authoritative Source)       │
│   - Resource Provider groups                │
│   - Organizations                            │
│   - Infrastructure resources                 │
└────────────────┬────────────────────────────┘
                 │
                 ▼
┌─────────────────────────────────────────────┐
│   Operations API Warehouse                   │
│   Database: cider.models.CiderGroups         │
│   REST API: operations-api.access-ci.org     │
└────────────────┬────────────────────────────┘
                 │ HTTP/JSON
                 ▼
┌─────────────────────────────────────────────┐
│   Django CMS (This App)                      │
│   Database: operations_portalcms_django.     │
│             models.CiderGroups               │
│   - Syncs from API via management command    │
│   - Creates RP groups & permissions          │
└─────────────────────────────────────────────┘
```

## Key CIDER API Endpoints

**1. Active Groups**
```
GET https://operations-api.access-ci.org/wh2/cider/v2/access-active-groups/
```
Returns Resource Provider groups, e.g.:
- `rp.psc.edu` (Pittsburgh Supercomputing Center)
- `rp.tacc.utexas.edu` (Texas Advanced Computing Center)
- `rp.sdsc.edu` (San Diego Supercomputer Center)

**2. Organizations**
```
GET https://operations-api.access-ci.org/wh2/cider/v1/organizations/
```
Returns organization metadata (names, URLs, logos)

**3. Infrastructure Resources**
```
GET https://operations-api.access-ci.org/wh2/cider/v2/access-active/
```
Returns compute/storage resources like Bridges-2, Delta, Stampede3

## Data Flow

### Development Workflow
```bash
# Load test data for development
uv run python manage.py load_test_cider_data

# Create RP permissions and groups
uv run python manage.py setup_rp_permissions
```

### Production Workflow
```bash
# Sync from live CIDER API
uv run python manage.py sync_cider_from_api

# Create RP permissions and groups
uv run python manage.py setup_rp_permissions
```

## What Gets Synced

### CiderGroups Model
Stores **Resource Provider organizations** (not individual resources):

| Field | Example | Source |
|-------|---------|--------|
| `info_groupid` | `rp.psc.edu` | CIDER API `info_groupid` |
| `group_descriptive_name` | `Pittsburgh Supercomputing Center` | CIDER API `group_descriptive_name` |
| `group_description` | Full description | CIDER API `group_description` |
| `info_resourceids` | `["bridges2-gpu.psc.access-ci.org", ...]` | CIDER API `rollup_info_resourceids` |

### CiderOrganizations Model
Stores **institution metadata**:

| Field | Example | Source |
|-------|---------|--------|
| `organization_abbrev` | `PSC` | CIDER API `organization_abbreviation` |
| `organization_name` | `Pittsburgh Supercomputing Center` | CIDER API `organization_name` |
| `organization_url` | `https://www.psc.edu` | CIDER API `organization_url` |

## Relationship to CILogon Permissions

**IMPORTANT:** CIDER data is **metadata only**. The actual permission sync happens via **CILogon** authentication:

1. **User logs in** → CILogon returns `isMemberOf` claim
2. **Signal handler** → Syncs URNs to Django groups
3. **Permission check** → Checks group membership

CIDER provides:
- ✅ Group existence validation
- ✅ Display names and metadata
- ✅ Resource associations

CIDER does NOT:
- ❌ Grant permissions directly
- ❌ Replace CILogon authentication
- ❌ Sync user group memberships

## Comparison: API Warehouse vs Django CMS

| Aspect | API Warehouse | Django CMS |
|--------|---------------|------------|
| **CIDER Import** | `from cider.models import CiderGroups` | `from operations_portalcms_django.models import CiderGroups` |
| **Database** | Authoritative CIDER DB | Copy synced from API |
| **Data Source** | Direct CIDER system | REST API from warehouse |
| **Purpose** | Serve CIDER data to ecosystem | Use CIDER data for RP permissions |
| **Sync Method** | Direct database sync | HTTP API calls |

## Sync Command Details

The `sync_cider_from_api.py` command:
- Fetches JSON from Operations API
- Filters for RP groups (`rp.*` prefix only)
- Updates or creates local CiderGroups records
- Syncs organization metadata
- Does NOT modify user permissions (run `setup_rp_permissions` separately)

## Future Enhancements

Potential improvements:
- **Scheduled sync** - Use Django celery/cron to auto-sync daily
- **Webhook notifications** - Get notified when CIDER data changes
- **Shared database** - Use Django multi-db to query warehouse directly
- **Infrastructure filtering** - Filter news by specific resources a user manages

## Related Documentation

- [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md) - How RP users can add/edit news
- [QUICKSTART_PERMISSIONS.md](QUICKSTART_PERMISSIONS.md) - Setup guide
- [PERMISSIONS.md](PERMISSIONS.md) - Technical implementation details
