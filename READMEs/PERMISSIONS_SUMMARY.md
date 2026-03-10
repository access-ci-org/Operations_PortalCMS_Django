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

**See:** [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md)

---

### 2. Custom Groups → CMS Pages
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
- **News** - Automatic (CILogon sync)
- **Pages** - Manual (admin assigns users to groups)

**Different needs:**
- **News** - RPs need to collaborate across sites
- **Pages** - Departments need isolated control

---

## Quick Reference

| I want to... | Use | Create | Assign |
|--------------|-----|--------|--------|
| Let RPs add status updates | RP groups | Auto (from CIDER) | Auto (CILogon) |
| Let PIs edit public pages | Custom group | Manual (`/admin/auth/group/`) | Manual (`/admin/auth/user/`) |
| Let managers edit focus areas | Custom group | Manual | Manual |
| Restrict internal pages | Custom group | Manual | Manual |

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
- [NEWS_PERMISSIONS.md](NEWS_PERMISSIONS.md) - How news permissions work
- [CMS_PAGE_PERMISSIONS.md](CMS_PAGE_PERMISSIONS.md) - How page permissions work

**Technical details:**
- [PERMISSIONS.md](PERMISSIONS.md) - Technical implementation
- [QUICKSTART_PERMISSIONS.md](QUICKSTART_PERMISSIONS.md) - Setup guide

**Testing:**
- `test_news_permissions.py` - Test news permissions
- `test_permissions.py` - Test RP group sync

---

## Summary

**✅ Clear separation of concerns**
- RP groups = News
- Custom groups = Pages

**✅ Simple and flexible**
- No complex matching rules
- Easy to understand

**✅ Ready to use**
- All code implemented
- All tests passing
