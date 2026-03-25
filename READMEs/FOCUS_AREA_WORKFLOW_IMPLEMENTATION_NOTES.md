# Focus Area Page Workflow Implementation - March 25, 2026

## 🚀 Quick Context (Read This First)
**Status**: Implementation COMPLETE, automated tests PASSING, ready for manual testing
**What**: Page-level edit/publish workflow for Focus Area pages using Django CMS built-in features
**Why**: Enable page-specific editors to edit but not publish; general editors can review and publish
**Next**: Manual user acceptance testing (see testing plan below)

> **Note**: This implementation is documented in detail at:
> **WORKFLOW_TESTING.md** - Comprehensive testing guide for all workflows

## What We Did Today
Implemented page-level submission/review/approval workflow for Focus Area pages using Django CMS built-in draft/publish capabilities.

**Key Decision**: Chose page-level workflow (NOT section-level) using Django CMS native features instead of custom workflow fields.

## Decision Journey (What We Tried)
1. **First Attempt**: Section-level workflow with custom fields (draft/pending_review/approved)
   - Added workflow fields to FocusAreaSection model (migration 0015)
   - Created workflow functions in workflow.py
   - Added section-level URLs in app_urls.py
   
2. **Pivot**: User clarified "no workflow on sections - just pages"
   - Removed all section-level workflow code (migration 0016)
   - Switched to Django CMS built-in page draft/publish system
   
3. **Final Implementation**: Page-level using PagePermission objects
   - Two-tier permission model (editors vs reviewers)
   - Combined PagePermission + Django model permissions
   - No custom fields needed - leverages CMS native capabilities

## Current State: COMPLETE ✅
- All code changes implemented
- Migrations applied (0015 add workflow, 0016 remove workflow - ended up using CMS native)
- Automated tests passing
- Documentation complete with setup commands
- **Git status**: Documentation committed and pushed

## Permission Model (Two-Tier)
1. **Page-Specific Editors** (e.g., Focus_STEP_Editors):
   - Can EDIT their specific focus area pages
   - CANNOT publish (can_publish=False in PagePermission)
   
2. **General Editors/Reviewers** (Focus_area_editors):
   - Can EDIT all focus area pages
   - CAN PUBLISH (can_publish=True in PagePermission)
   - Acts as reviewer/approver role

## Setup Commands (Already Documented)
```bash
# 1. Configure groups and base CMS permissions
python manage.py setup_groups

# 2. Configure page-specific permissions
python manage.py setup_focus_area_page_permissions

# 3. Run automated tests
python tests/test_focus_area_page_workflow.py
```

## Tomorrow's Testing Plan
### Manual Testing Checklist:
1. **As STEP Editor** (page-specific editor):
   - Log in as user in Focus_STEP_Editors group
   - Navigate to STEP focus area page in CMS
   - Make content changes (should work)
   - Try to publish (should be BLOCKED)
   - Submit for review

2. **As General Editor** (reviewer):
   - Log in as user in Focus_area_editors group
   - View pending changes from STEP editor
   - Review content
   - Approve and publish (should work)

3. **Verify Isolation**:
   - STEP editor should NOT be able to edit Cybersecurity pages
   - Cybersecurity editor should NOT be able to edit STEP pages
   - General editors should be able to edit/publish ALL focus area pages

## Key Files to Reference
- **Setup Commands**: operations_portalcms_django/management/commands/setup_groups.py, setup_focus_area_page_permissions.py
- **Tests**: tests/test_focus_area_page_workflow.py
- **Documentation**: FOCUS_AREA_WORKFLOW.md (primary), SETUP_GUIDE.md (comprehensive), WORKFLOW_TESTING.md (testing procedures)
- **Models**: operations_portalcms_django/models.py (FocusAreaSection - no workflow fields)

## How It Works Technically
- Django CMS pages have built-in draft state
- PagePermission objects control who can edit/publish specific pages
- Model-level permissions (change_page, publish_page) required + PagePermission objects
- Grant type: ACCESS_PAGE_AND_DESCENDANTS (page + all children)
- No custom workflow fields needed on models

## Groups Configured
- Focus_area_editors (reviewers - can publish)
- Focus_STEP_Editors (edit only STEP pages)
- Focus_Cybersecurity_Editors (edit only Cybersecurity pages)
- Focus_Facilities_Editors (edit only Facilities pages)
- Focus_DesktopSupport_Editors (edit only Desktop Support pages)

## If Issues Found Tomorrow
1. Check Django CMS permissions: User and Group Permissions → Pages
2. Verify group membership: Admin → Users → Group memberships
3. Run tests again: `python tests/test_focus_area_page_workflow.py`
4. Check logs for permission denials
5. Review: FOCUS_AREA_WORKFLOW.md troubleshooting section

## 📋 Next Steps (Action Items)
1. **Run automated tests** to verify everything still works:
   ```bash
   python tests/test_focus_area_page_workflow.py
   ```

2. **Manual UAT** (see "Tomorrow's Testing Plan" above):
   - Test as STEP editor (edit only, no publish)
   - Test as general editor (edit + publish)
   - Verify permission isolation

3. **If issues found**: Use troubleshooting guide in WORKFLOW_TESTING.md

4. **When satisfied**: Mark workflow implementation as production-ready
