# News Permissions

This project uses explicit Django groups for each news type with a two-tier model: Authors write and submit for review; Managers review, publish, and have full control.

## News Roles

Each news type has two roles:

- `Authors` - can create and edit items; must submit for review to publish
- `Managers` - can create, edit, delete, review, and publish items directly

The groups created by `setup_groups` are:

- `System Status Authors`
- `System Status Managers`
- `Integration News Authors`
- `Integration News Managers`

## Permission Matrix

| Group | View | Add | Change | Delete | Review | Publish |
|------|------|-----|--------|--------|--------|---------|
| System Status Authors | Yes | Yes | Yes | No | No | No |
| System Status Managers | Yes | Yes | Yes | Yes | Yes | Yes |
| Integration News Authors | Yes | Yes | Yes | No | No | No |
| Integration News Managers | Yes | Yes | Yes | Yes | Yes | Yes |

## Django Permission Mapping

### System Status News

- Default Django permissions:
  - `view_systemstatusnews`
  - `add_systemstatusnews`
  - `change_systemstatusnews`
  - `delete_systemstatusnews`
- Custom workflow permissions:
  - `can_review_systemstatusnews`
  - `can_publish_systemstatusnews`

### Integration News

- Default Django permissions:
  - `view_integrationnews`
  - `add_integrationnews`
  - `change_integrationnews`
  - `delete_integrationnews`
- Custom workflow permissions:
  - `can_review_integrationnews`
  - `can_publish_integrationnews`

## Workflow Notes

- Authors can create drafts and edit news items; they cannot publish directly.
- Authors submit a news item for review by changing its status to `pending_review`; a Manager then publishes it.
- Managers are the only non-superuser role with `can_review_*` and `can_publish_*` permissions.
- Managers can publish directly without a formal review step if the situation warrants it.
- The `Publishers` tier has been retired. Any existing Publisher group members should be migrated to the appropriate Managers group (see Legacy Migration below).

## Current Behavior Notes

- The current edit views are gated by Django's `change_*` permission.
- That means users in `Authors` or `Managers` can edit news items of that type, not only items they personally authored.
- Submitting an item for review is still limited to the item's author.

## Setup

### Initial Configuration

Run these commands to configure news workflow groups and permissions:

```bash
# 1. Configure news workflow groups and permissions
uv run python manage.py setup_groups

# This creates:
#   - System Status Authors / System Status Managers
#   - Integration News Authors / Integration News Managers
#   - Assigns appropriate permissions to each group
```

### Adding Users to Groups

After running setup_groups, assign users to the appropriate groups:

1. Go to Django Admin: `/admin/`
2. Navigate to: **Authentication and Authorization → Groups**
3. Select the appropriate group (e.g., `System Status Authors`)
4. Add users to the group
5. Save

### Testing

Verify the workflow is configured correctly:

```bash
uv run python tests/test_news_permissions.py
```

---

## Legacy Migration

If you have legacy editor groups or the retired Publishers groups:

**Legacy groups (migrate and remove):**
- `System Status Editors`
- `System Status Publishers`
- `Integration News Editors`
- `Integration News Publishers`
- `All News Editors`

**All legacy groups map to their respective Managers group.** The `setup_groups` command handles this automatically.

**Migration commands:**

```bash
# Migrate users from legacy/publisher groups to manager groups
uv run python manage.py setup_groups --migrate-legacy-memberships

# Delete legacy groups (after verifying migration)
uv run python manage.py setup_groups --delete-legacy-groups

# Or do both in one run:
uv run python manage.py setup_groups --migrate-legacy-memberships --delete-legacy-groups
```

---

## Testing Strategy

Recommended test flow:

1. Assign one user to an `Authors` group
2. Assign one user to a `Managers` group
3. Test the workflow:
   - Authors can create drafts and edit
   - Authors can submit for review (status → `pending_review`)
   - Authors cannot publish directly
   - Managers can publish items directly
   - Managers can review and approve items in `pending_review` state

Run automated tests:

```bash
uv run python tests/test_news_permissions.py
```

---

## Related Documentation

- [Focus Area Workflow](./FOCUS_AREA_WORKFLOW.md) - Page-level workflow for focus areas
- [Permissions Summary](./PERMISSIONS_SUMMARY.md) - Overview of all permission systems
- [Permissions Technical Details](./PERMISSIONS.md) - Implementation details

## Admin Notes

Use Django Admin to assign users to the new groups:

- `/admin/auth/group/`
- `/admin/auth/user/`

For a small team, this setup keeps the roles easy to reason about while still letting you test draft, publish, and review workflows separately.
