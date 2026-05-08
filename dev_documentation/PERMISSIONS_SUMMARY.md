# Permissions System - Summary

## Simple Permission Model

The Operations Portal CMS uses **two separate permission systems**:

Last checked against RDS `portal1`: 2026-05-08. See [CURRENT_STATE.md](./CURRENT_STATE.md) for the full verification snapshot.

### 1. RP Groups → News Items
**What:** Resource Provider (RP) groups from CILogon  
**Controls:** Who can add/edit news items  
**How:** Automatic sync from COmanage group memberships  

**Rule:** If you're in ANY RP group, you can add/edit both types of news:
- ✅ System Status News
- ✅ Integration News

**Groups:**
- `urn:group:access-ci.org:rp.psc.edu:coordinator`
- `urn:group:access-ci.org:rp.tacc.utexas.edu:implementer`
- etc.

### 1a. News Workflow Groups
**What:** Explicit Django groups for news workflow roles  
**Controls:** Author, publish, and manage/review responsibilities  
**How:** Configured via `setup_groups` command, users assigned manually  

**Groups (two tiers per news type):**
- `System Status Authors` - Can create and edit; must submit for review to publish
- `System Status Managers` - Can create, edit, delete, review, and publish
- `Integration News Authors` - Can create and edit; must submit for review to publish
- `Integration News Managers` - Can create, edit, delete, review, and publish

**Note:** The former `Publishers` tier (System Status Publishers, Integration News Publishers) has been retired. Publisher users should be migrated to the corresponding Managers group.

**See:** [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)

---

### 2. Focus Area Page Workflow
**What:** Django CMS page-level draft/publish workflow for focus areas  
**Controls:** Who can edit vs. publish focus area pages  
**How:** Configured via `setup_groups`, `setup_focus_area_page_permissions`, and `djangocms_versioning` in the active environment  

**Groups:**
- Page-specific editors (e.g., `Focus_STEP_Editors`) - Can edit but NOT publish
- `Focus_area_editors` - Can edit AND publish any focus area

**Current verified state:**
- `djangocms_versioning` is installed and active
- page-specific focus groups can edit assigned focus pages but cannot publish
- `Focus_area_editors` can edit and publish focus pages
- RDS `portal1` currently has 18 published CMS versions and 8 unpublished versions

**See:** [FOCUS_AREA_WORKFLOW.md](FOCUS_AREA_WORKFLOW.md)

---

### 3. Custom Groups → CMS Pages
**What:** Custom Django groups created by admins  
**Controls:** Who can  edit specific CMS pages  
**How:** Manual group creation and assignment  

**Examples:**
- "PI Editors" → Can edit public pages
- "Cybersecurity Managers" → Can edit /focus-areas/cybersecurity/
- "Operations Staff" → Can edit internal pages

**See:** [CMS_PAGE_PERMISSIONS.md](CMS_PAGE_PERMISSIONS.md)

---

## Why Separate?

**Different use cases:**
- **News** - Fast, collaborative, RP-driven content
- **Pages** - Slower, structured, department-driven content

**Different workflows:**
- **News** - Automatic access from RP groups, plus manual workflow roles for publishing/review
- **Pages** - Manual (admin assigns users to groups)

**Different needs:**
- **News** - RPs need to collaborate across sites
- **Pages** - Departments need isolated control

---

## Quick Reference

| I want to... | Use | Setup Command | Assign |
|--------------|-----|---------------|--------|
| Configure news workflow | News workflow groups | `setup_groups` | Manual (`/admin/auth/user/`) |
| Configure focus area workflow | Focus area groups | `setup_groups` + `setup_focus_area_page_permissions` | Manual |
| Let RPs add status updates | RP groups | `sync_cider_from_api --dry-run`, then `setup_rp_permissions --dry-run` before scope-reviewed writes | Auto (CILogon) |
| Let PIs edit public pages | Custom group | Manual (`/admin/auth/group/`) | Manual |
| Let managers edit focus areas | Custom group | Manual | Manual |

---

## Setup Commands Summary

### Initial Setup (Run Once)

```bash
# 1. Configure news and focus area workflow groups
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_groups

# 2. Configure focus area page-specific permissions
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_focus_area_page_permissions

# 3. Configure RP permissions after confirming intended CIDER group scope
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_rp_permissions --dry-run

# 4. Load test data for local development only
uv run python manage.py load_test_cider_data
```

### Reconfiguration (Safe to re-run)

All setup commands are idempotent and safe to re-run:

```bash
# Update all permissions
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_groups
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
uv run python manage.py setup_focus_area_page_permissions
```

---

## Testing

Verify configurations:

```bash
# Test news workflow
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_news_permissions.py

# Test focus area page workflow
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_focus_area_page_workflow.py
```

The scripts in `tests/` mutate the configured database; do not run them against RDS `portal1` unless that is intentional.

---

## Files to Delete

Already removed:
- ✅ `create_rp_pages.py` - Was for RP page creation, not needed

Keep:
- ✅ `setup_rp_permissions.py` - Needed for RP news permissions
- ✅ `load_test_cider_data.py` - Needed for testing
- ✅ All admin.py modifications - Needed for news permissions
- ✅ utils.py - Needed for permission checks

---

## Documentation

**Start here:**
- [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md) - News workflow with draft/review/publish
- [FOCUS_AREA_WORKFLOW.md](FOCUS_AREA_WORKFLOW.md) - Focus area page workflow
- [CMS_PAGE_PERMISSIONS.md](CMS_PAGE_PERMISSIONS.md) - General CMS page permissions

**Technical details:**
- [PERMISSIONS.md](PERMISSIONS.md) - Technical implementation
- [QUICKSTART_PERMISSIONS.md](QUICKSTART_PERMISSIONS.md) - RP permissions setup

**Testing:**
- `test_news_permissions.py` - Test news permissions
- `test_permissions.py` - Test RP group sync
- [CURRENT_STATE.md](./CURRENT_STATE.md) - Read-only verification snapshot

---

## Summary

**✅ Clear separation of concerns**
- RP groups = News
- Custom groups = Pages

**✅ Focus-area versioning active in the current runtime**
- `djangocms_versioning` is sufficient for the tested STEP draft/publish workflow
- `djangocms_moderation` is not enabled

**✅ Simple and flexible**
- No complex matching rules
- Easy to understand

**✅ Ready for normal use**
- Core Django checks pass
- RDS schema and ownership checks pass
- Standalone mutating test scripts should be reserved for clone/test databases
