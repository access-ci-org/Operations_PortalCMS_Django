# Focus Area Block-Level Permissions

## Overview

This document describes the current block-level permission foundation for the focus-area pages in Django CMS.

It is the follow-on to the existing page-level permission model documented in [FOCUS_AREA_PERMS.md](./FOCUS_AREA_PERMS.md).

The important distinction is:

- page-level permissions decide who can edit a focus-area page at all
- block-level permissions decide which managed sections on that page a user can edit

## Current State

### Page-Level Permissions

Page permissions were already in place before this block-level work:

- `Focus_area_editors` has page-level edit rights across all four main focus-area pages
- each page-specific focus group has page-level edit rights on its matching page
- this behavior is configured by [setup_focus_area_page_permissions.py](../operations_portalcms_django/management/commands/setup_focus_area_page_permissions.py)

### Block-Level Foundation Now Implemented

The first block-level governance layer is now in place.

Implemented:

- a managed `FocusAreaSection` model
- stable section identifiers via `section_key`
- section ownership via `owner_group`
- a reusable permission helper for section editing
- a Django admin entry point for editing managed sections
- template loading/rendering for managed sections on `focus_area.html`
- safe fallback to legacy placeholders when no managed section record exists yet

Not implemented yet:

- seeded section records for every focus-area page
- migration of old placeholder content into managed section records
- section-specific front-end edit links
- workflow/review/publish states for focus-area sections
- governance of `hero_image`

## Why This Was Needed

Before this change, [focus_area.html](../templates/focus_area.html) used only raw Django CMS placeholders for the editable sections:

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

That meant:

- placeholder content lived directly in the page
- page-level edit access implicitly allowed editing every section on that page
- there was no durable block identity to attach ownership to
- there was no clean place to store per-section metadata like `owner_group` or future workflow fields

Raw placeholders are a poor fit for true governed block ownership. The new model-backed approach gives each governed section a stable identity and explicit ownership.

## Implemented Design

### Logical Editable Units

The focus-area page is now treated as these logical units:

- `hero_image`
- `section_1`
- `section_2`
- `section_3`
- `section_4`
- `section_5`
- `additional_links`

The key design choice is that heading and body are governed together as one section record.

That means:

- `section_1_heading` and `section_1_content` are no longer treated as separate permission targets
- the permission target is the managed section record for `section_1`
- the same rule applies to `section_2` through `section_5`

`hero_image` remains a normal CMS placeholder for now.

### Model

The new model is:

- `FocusAreaSection`

It was added in [models.py](../operations_portalcms_django/models.py) and created in migration [0013_focusareasection.py](../operations_portalcms_django/migrations/0013_focusareasection.py).

Current fields:

- `page`
  - foreign key to `cms.Page`
- `section_key`
  - choices:
    - `section_1`
    - `section_2`
    - `section_3`
    - `section_4`
    - `section_5`
    - `additional_links`
- `heading`
- `body`
  - stored as rich HTML content
- `owner_group`
  - foreign key to Django `Group`
- `is_active`
- `updated_at`
- `updated_by`

Uniqueness rule:

- one row per `page + section_key`

This gives each governed block a stable, permissionable identity.

## Permission Model

### Page Layer

The page layer is unchanged:

- `Focus_area_editors` can edit all four focus-area pages
- each page-specific focus editor group can edit its matching page

### Section Layer

The new section-level edit rule is implemented by `can_edit_focus_area_section(user, section)` in [utils.py](../operations_portalcms_django/utils.py).

A user can edit a managed section if:

- the user is a superuser
- the user is in `Focus_area_editors`
- the user is in that section's `owner_group`

This gives us block-level ownership without replacing the existing page-level structure.

### Admin Enforcement

The new admin registration in [admin.py](../operations_portalcms_django/admin.py) applies that permission model in practice.

Current admin behavior:

- superusers can see and edit all `FocusAreaSection` records
- `Focus_area_editors` can see and edit all `FocusAreaSection` records
- page-specific focus groups can see and edit only the records owned by their group
- `updated_by` is set automatically on save

This is a practical first version because it provides governed editing immediately without requiring a custom section-edit UI.

## Rendering Model

Managed sections are now loaded through a template tag in [focus_area_sections.py](../operations_portalcms_django/templatetags/focus_area_sections.py).

Current rendering flow:

1. Get the current CMS page from template context.
2. Load active `FocusAreaSection` rows for that page.
3. Build a dictionary keyed by `section_key`.
4. Render those managed sections in [focus_area.html](../templates/focus_area.html).

The template now prefers managed section records for:

- `section_1`
- `section_2`
- `section_3`
- `section_4`
- `section_5`
- `additional_links`

`hero_image` still renders as:

```django
{% placeholder "hero_image" %}
```

## Transitional Fallback Behavior

This first implementation intentionally preserves a migration-friendly fallback.

If a managed section record exists:

- the template renders `heading` and `body` from `FocusAreaSection`

If no managed section record exists yet:

- the template falls back to the old placeholder content

This is important because it lets us:

- deploy the structural change first
- apply the migration safely
- seed and migrate section content incrementally
- avoid breaking the existing focus-area pages while content is still being moved

## How The Work Was Implemented

The block-level foundation was implemented in these pieces:

- [models.py](../operations_portalcms_django/models.py)
  - added `FocusAreaSection`
- [0013_focusareasection.py](../operations_portalcms_django/migrations/0013_focusareasection.py)
  - created the database table
- [utils.py](../operations_portalcms_django/utils.py)
  - added `can_edit_focus_area_section`
- [admin.py](../operations_portalcms_django/admin.py)
  - registered `FocusAreaSectionAdmin`
  - enforced section-level edit checks
- [focus_area_sections.py](../operations_portalcms_django/templatetags/focus_area_sections.py)
  - loads managed sections for the current page
- [focus_area.html](../templates/focus_area.html)
  - now renders managed sections first, placeholders second

## Why This Approach Was Chosen

This approach was chosen because it balances correctness, safety, and incremental delivery.

Benefits:

- preserves the existing page-level permission model
- introduces real block identity through `page + section_key`
- supports explicit ownership through `owner_group`
- avoids trying to force block-level governance into raw placeholders
- gives the team an admin-editable first version quickly
- supports future expansion into review, approval, publishing, and audit metadata
- allows gradual migration because the old placeholders still work as fallback

## Current Ownership Strategy

The intended ownership mapping remains:

- `CyberSecurity` sections -> `Focus_Cybersecurity_Editors`
- `Data Transfer and Networking Support` sections -> `Focus_Networking_dataTransfer_Editors`
- `Operational Support` sections -> `Focus_operationsSupport_Editors`
- `Student Training and Engagement Program` sections -> `Focus_STEP_Editors`

`Focus_area_editors` remains the broad override group across all focus-area content.

## What Still Needs To Happen

The foundation is in place, but the full block-level rollout is not finished yet.

Next steps:

1. Seed `FocusAreaSection` rows for each existing focus-area page.
2. Assign `owner_group` on each section row according to the focus page.
3. Move the existing placeholder content into the managed section records.
4. Validate that rendered output matches the current pages.
5. Decide whether to remove old placeholder usage after migration is complete.
6. Decide whether `hero_image` should remain a placeholder or become governed later.
7. Add workflow fields only if section-level review/publish behavior becomes necessary.

## Recommended Current Mental Model

The cleanest way to think about the system now is:

- page permissions are the outer access layer
- `FocusAreaSection` records are the inner governed block layer
- the true block identity is `page + section_key`
- ownership is attached to the section record through `owner_group`

That is the core of the implemented block-level permissions design.
