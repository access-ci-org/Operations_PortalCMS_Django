# Focus Area Page Workflow Implementation Notes

## Current Status

This note reflects the current implemented direction after the section-model cleanup.

- focus-area workflow is page-level only
- page-specific editor groups can edit assigned focus pages
- `Focus_area_editors` remains the reviewer/publisher group
- focus pages render from Django CMS placeholders/plugins only
- legacy `FocusAreaSection` code and data have been retired
- `djangocms_versioning` is installed and active in the current RDS-backed runtime

## What Survived From Earlier Work

- `setup_groups`
- `setup_focus_area_page_permissions`
- the two-tier page permission model
- public visibility via `CMS_PUBLIC_FOR = 'all'`

## What Was Retired

- block-level focus-area groups
- `FocusAreaSection`
- managed section rendering in `focus_area.html`
- section-oriented editing and permission logic

## Source Of Truth

For current workflow behavior, use:

- [FOCUS_AREA_WORKFLOW.md](./FOCUS_AREA_WORKFLOW.md)
- [WORKFLOW_TESTING.md](./WORKFLOW_TESTING.md)
- [CMS_VERSIONING_SKETCH.md](./CMS_VERSIONING_SKETCH.md)

## Current Architectural Direction

The project is now positioned for one content path:

1. Django CMS page content
2. page-level edit/review/publish roles
3. Django CMS versioning against that page content only
