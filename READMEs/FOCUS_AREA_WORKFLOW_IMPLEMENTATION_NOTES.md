# Focus Area Page Workflow Implementation - March 25, 2026

## 🚀 Quick Context (Read This First)
**Status**: Working demo configuration validated after follow-up fixes
**What**: Page-level edit/publish workflow for Focus Area pages using Django CMS built-in features
**Why**: Enable page-specific editors to edit but not publish; general editors can review and publish while focus pages remain publicly viewable
**Next**: Use `WORKFLOW_TESTING.md` as the source of truth for demo testing

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

## Current State
- Page-level workflow is the intended and tested model
- STEP block editing is not the correct path for review workflow testing
- Focus-area pages should remain publicly viewable
- `Focus_STEP_Editors` can edit STEP but should not publish
- `Focus_area_editors` remains the reviewer/publisher group

## Permission Model (Two-Tier)
1. **Page-Specific Editors** (e.g., Focus_STEP_Editors):
   - Can EDIT their specific focus area pages
   - CANNOT publish (can_publish=False in PagePermission)
   
2. **General Editors/Reviewers** (Focus_area_editors):
   - Can EDIT all focus area pages
   - CAN PUBLISH (can_publish=True in PagePermission)
   - Acts as reviewer/approver role

## Follow-Up Fixes Applied After Initial Implementation
- Added the CMS structure/plugin permissions needed for standard Django CMS page editing
- Cleaned malformed mixed user/group `cms_pagepermission` rows for STEP
- Kept focus-area `PagePermission.can_view=False` so editor groups do not gate anonymous page access
- Enabled `CMS_PUBLIC_FOR = 'all'` so focus pages remain publicly viewable
- Removed STEP from the active managed block editing path for workflow testing purposes

## Setup Commands (Already Documented)
```bash
# 1. Configure groups and base CMS permissions
python manage.py setup_groups

# 2. Configure page-specific permissions
python manage.py setup_focus_area_page_permissions

# 3. Run automated tests
python tests/test_focus_area_page_workflow.py
```

## Final Testing Guidance
Use `READMEs/WORKFLOW_TESTING.md` for the current manual testing checklist.

The validated demo pattern is:
1. Logged out: focus-area pages remain publicly viewable
2. `Focus_STEP_Editors`: can edit STEP in standard CMS page edit mode and save draft
3. `Focus_STEP_Editors`: cannot publish STEP
4. Logged out/incognito: public STEP page does not change until reviewer publish
5. `Focus_area_editors`: can review and publish

## Key Files to Reference
- **Setup Commands**: operations_portalcms_django/management/commands/setup_groups.py, setup_focus_area_page_permissions.py
- **Tests**: tests/test_focus_area_page_workflow.py
- **Documentation**: FOCUS_AREA_WORKFLOW.md (primary), SETUP_GUIDE.md (comprehensive), WORKFLOW_TESTING.md (testing procedures)
- **Models**: operations_portalcms_django/models.py (FocusAreaSection - no workflow fields)

## How It Works Technically
- Django CMS pages have built-in draft state
- PagePermission objects control who can edit/publish specific pages
- Model-level permissions plus CMS structure/plugin permissions are required for standard page editing
- `CMS_PUBLIC_FOR = 'all'` keeps the pages publicly viewable
- Grant type: ACCESS_PAGE_AND_DESCENDANTS (page + all children)
- No custom workflow fields needed on models

## Groups Configured
- Focus_area_editors (reviewers - can publish)
- Focus_STEP_Editors (edit only STEP pages)
- Focus_Cybersecurity_Editors (edit only Cybersecurity pages)
- Focus_Networking_dataTransfer_Editors (edit only Data Transfer and Networking Support pages)
- Focus_operationsSupport_Editors (edit only Operational Support pages)

## Source Of Truth
For current workflow behavior, troubleshooting, and demo steps, use:

- `READMEs/WORKFLOW_TESTING.md`
- `READMEs/FOCUS_AREA_WORKFLOW.md`
