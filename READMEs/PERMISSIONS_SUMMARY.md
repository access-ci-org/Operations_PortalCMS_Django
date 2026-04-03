# Permissions System - Summary

## Simple Permission Model

The Operations Portal CMS uses **two separate permission systems**:

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

**Groups:**
- `System Status Authors` - Can create and edit
- `System Status Publishers` - Can create, edit, and publish
- `System Status Managers` - Can create, edit, delete, review, and publish
- `Integration News Authors` - Can create and edit
- `Integration News Publishers` - Can create, edit, and publish
- `Integration News Managers` - Can create, edit, delete, review, and publish

**See:** [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)

---

### 2. Focus Area Page Workflow
**What:** Django CMS page-level draft/publish workflow for focus areas  
**Controls:** Who can edit vs. publish focus area pages  
**How:** Configured via `setup_groups`, `setup_focus_area_page_permissions`, and `djangocms_versioning` in the active environment  

**Groups:**
- Page-specific editors (e.g., `Focus_STEP_Editors`) - Can edit but NOT publish
- `Focus_area_editors` - Can edit AND publish any focus area

**Verified clone result (2026-04-03):**
- a page-specific editor can create a draft for STEP
- the published page remains separate until publish
- reviewer/superuser can publish successfully
- the old live version becomes `unpublished` after publish

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
| Let RPs add status updates | RP groups | `setup_rp_permissions` + `load_test_cider_data` | Auto (CILogon) |
| Let PIs edit public pages | Custom group | Manual (`/admin/auth/group/`) | Manual |
| Let managers edit focus areas | Custom group | Manual | Manual |

---

## Setup Commands Summary

### Initial Setup (Run Once)

```bash
# 1. Configure news and focus area workflow groups
uv run python manage.py setup_groups

# 2. Configure focus area page-specific permissions
uv run python manage.py setup_focus_area_page_permissions

# 3. Configure RP permissions (optional - for news access)
uv run python manage.py setup_rp_permissions

# 4. Load test data for development (optional)
uv run python manage.py load_test_cider_data
```

### Reconfiguration (Safe to re-run)

All setup commands are idempotent and safe to re-run:

```bash
# Update all permissions
uv run python manage.py setup_groups
uv run python manage.py setup_focus_area_page_permissions
```

---

## Testing

Verify configurations:

```bash
# Test news workflow
uv run python tests/test_news_permissions.py

# Test focus area page workflow
uv run python tests/test_focus_area_page_workflow.py
```

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

---

## Summary

**✅ Clear separation of concerns**
- RP groups = News
- Custom groups = Pages

**✅ Focus-area versioning now proven in clone**
- `djangocms_versioning` is sufficient for the tested STEP draft/publish workflow
- `djangocms_moderation` is still optional and not yet enabled

**✅ Simple and flexible**
- No complex matching rules
- Easy to understand

**✅ Ready to use**
- All code implemented
- All tests passing
