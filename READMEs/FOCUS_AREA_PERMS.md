# Focus Area Page Permissions

## Overview

This document describes the **current page-level permission model** for the four main focus-area pages in Django CMS.

This README is intended to stay aligned with the actual live configuration as development continues.

It covers:

- which focus editor groups exist
- which focus-area pages they control
- the current page-level permission flags in use
- the management command used to keep those permissions configured consistently

This document covers **page-level permissions only**.

It does **not** yet define a block-level permission system for the placeholders in [focus_area.html](../templates/focus_area.html). Block-level permissions will require managed section/plugin objects rather than plain placeholders.

## Current Focus Editor Groups

The following Django groups are currently used for focus-area editing:

- `Focus_area_editors`
- `Focus_Cybersecurity_Editors`
- `Focus_Networking_dataTransfer_Editors`
- `Focus_STEP_Editors`
- `Focus_operationsSupport_Editors`

### Intended Meaning

These groups are used as follows:

- `Focus_area_editors`
  - Broad editor group for **all four** main focus-area pages
  - Acts as the cross-focus-area editor/override group at the page level

- `Focus_Cybersecurity_Editors`
  - Page-level editor group for the **CyberSecurity** focus-area page

- `Focus_Networking_dataTransfer_Editors`
  - Page-level editor group for the **Data Transfer and Networking Support** focus-area page

- `Focus_STEP_Editors`
  - Page-level editor group for the **Student Training and Engagement Program** focus-area page

- `Focus_operationsSupport_Editors`
  - Page-level editor group for the **Operational Support** focus-area page

## Current Focus-Area Pages

The four main focus-area pages currently wired into the page-permission model are:

- `CyberSecurity`
- `Data Transfer and Networking Support`
- `Operational Support`
- `Student Training and Engagement Program`

These are Django CMS pages using the `focus_area.html` template under the `Focus Areas` section.

## Current Page-Level Permission Matrix

The current live page-level mapping is:

| Focus-Area Page | Broad Group | Page-Specific Group |
|-----------------|-------------|---------------------|
| `CyberSecurity` | `Focus_area_editors` | `Focus_Cybersecurity_Editors` |
| `Data Transfer and Networking Support` | `Focus_area_editors` | `Focus_Networking_dataTransfer_Editors` |
| `Operational Support` | `Focus_area_editors` | `Focus_operationsSupport_Editors` |
| `Student Training and Engagement Program` | `Focus_area_editors` | `Focus_STEP_Editors` |

This means each focus-area page currently has:

- one **global focus-area editor group**
- one **matching page-specific editor group**

## Current Permission Flags

Each of the configured focus-area page-permission records currently uses the same settings:

- `grant_on = 5`
  - Django CMS meaning: **Page and descendants**

- `can_add = True`
- `can_change = True`
- `can_move_page = True`
- `can_delete = False`
- `can_publish = False`
- `can_change_permissions = False`
- `can_view = False`

### Practical Meaning

With the current configuration:

- focus editors can edit the assigned focus-area page
- focus editors can add child pages beneath the assigned focus-area page
- focus editors can move pages in the allowed scope
- focus editors do **not** get delete rights from this page-permission setup
- focus editors do **not** get publish rights from this page-permission setup
- focus editors do **not** get permission-management rights from this page-permission setup
- public viewing is **not** restricted by these page-permission entries

This is intentional: the current setup is focused on **editing access**, not publishing or permission administration.

## How The Current Setup Is Applied

The current focus-area page permissions are configured by the management command:

- [setup_focus_area_page_permissions.py](../operations_portalcms_django/management/commands/setup_focus_area_page_permissions.py)

Run it with:

```bash
.venv/bin/python manage.py setup_focus_area_page_permissions
```

Preview changes without saving:

```bash
.venv/bin/python manage.py setup_focus_area_page_permissions --dry-run
```

## Why We Use A Command

The management command gives us a repeatable and documented way to keep permissions aligned with the intended model.

Benefits:

- avoids one-off manual CMS permission drift
- keeps all four focus-area pages configured consistently
- makes it easier to reapply permissions in another environment
- gives us a single source of truth for the current page-level mapping

## Current Scope: Page Level Only

At this stage, the focus-area permission model is implemented at the **page level** only.

That means:

- if a user has page edit rights on a focus-area page, they can edit the page’s content through Django CMS
- the current `focus_area.html` template placeholders are **not** individually permissioned

The current page-level system is the foundation for later block-level work.

## Future Direction: Block-Level Permissions

The current template [focus_area.html](../templates/focus_area.html) contains multiple placeholders such as:

- `hero_image`
- `section_1_heading`
- `section_1_content`
- `section_2_heading`
- `section_2_content`
- `section_3_heading`
- `section_3_content`
- `section_4_heading`
- `section_4_content`
- `section_5_heading`
- `section_5_content`
- `additional_links`

These placeholders do not currently have a separate permission model.

If block-level permissions are needed in the future, the recommended approach is:

1. Keep the current page-level groups and page-level permissions.
2. Convert selected sections into managed content objects or custom plugins.
3. Reuse the same focus editor groups as block owners.
4. Let `Focus_area_editors` remain the broad override/editor group across all focus-area content.

## Maintenance Notes

When updating focus-area permissions in development:

1. Update the management command if the intended mapping changes.
2. Re-run the command to apply the updated configuration.
3. Update this README if:
   - focus group names change
   - page titles change
   - page-level permission flags change
   - new focus-area pages are added
   - publish/delete/permission-management rights are expanded

## Related Documentation

- [CMS_PAGE_PERMISSIONS.md](./CMS_PAGE_PERMISSIONS.md)
- [PERMISSIONS_SUMMARY.md](./PERMISSIONS_SUMMARY.md)
