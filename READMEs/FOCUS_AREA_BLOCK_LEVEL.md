# Focus Area Block-Level Permissions

## Status

This document is kept only as historical context.

Block-level focus-area permissions are no longer part of the active architecture.

Current state:

- focus-area workflow is page-level only
- focus pages render from Django CMS placeholders/plugins
- `FocusAreaSection` has been retired from code and removed from the database
- section-level groups and permissions have been removed

## What To Use Instead

Use these documents as the current source of truth:

- [FOCUS_AREA_WORKFLOW.md](./FOCUS_AREA_WORKFLOW.md)
- [WORKFLOW_TESTING.md](./WORKFLOW_TESTING.md)
- [CMS_VERSIONING_SKETCH.md](./CMS_VERSIONING_SKETCH.md)

## Historical Note

Earlier work explored a model-backed section system for governed blocks inside `focus_area.html`.
That direction was abandoned because it introduced a second content path that would complicate
versioning, moderation, and page workflow.

The project now standardizes on:

1. CMS page-level permissions
2. CMS placeholder/plugin content
3. future Django CMS versioning for page content only
