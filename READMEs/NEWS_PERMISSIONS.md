# News Permissions

This project now uses explicit Django groups for each news type rather than one broad "editor" role.

## News Roles

Each news type has three roles:

- `Authors` - can create and edit items
- `Publishers` - can create, edit, and publish items
- `Managers` - can create, edit, delete, review, and publish items

The groups created by `setup_groups` are:

- `System Status Authors`
- `System Status Publishers`
- `System Status Managers`
- `Integration News Authors`
- `Integration News Publishers`
- `Integration News Managers`

## Permission Matrix

| Group | View | Add | Change | Delete | Review | Publish |
|------|------|-----|--------|--------|--------|---------|
| System Status Authors | Yes | Yes | Yes | No | No | No |
| System Status Publishers | Yes | Yes | Yes | No | No | Yes |
| System Status Managers | Yes | Yes | Yes | Yes | Yes | Yes |
| Integration News Authors | Yes | Yes | Yes | No | No | No |
| Integration News Publishers | Yes | Yes | Yes | No | No | Yes |
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

- Authors can create drafts and update news items.
- Publishers can publish content directly during create or update, and can publish items already in review.
- Managers are the only non-superuser role with the explicit `can_review_*` permissions.
- Managers already include publish capability, so users do not need both `Publishers` and `Managers` for the same news type.
- `can_publish_*` does not imply `add_*` or `change_*`; publisher groups include those permissions on purpose.

## Current Behavior Notes

- The current edit views are gated by Django's `change_*` permission.
- That means users in `Authors`, `Publishers`, or `Managers` can edit news items of that type, not only items they personally authored.
- Submitting an item for review is still limited to the item's author.

## Setup

Create or refresh the groups:

```bash
uv run python manage.py setup_groups
```

## Testing Strategy

Recommended test flow:

1. Assign one user to an `Authors` group.
2. Assign one user to a `Publishers` group.
3. Assign one user to a `Managers` group.
4. Verify:
   - Authors can draft and edit.
   - Publishers can draft and publish.
   - Managers can approve/reject and fully manage content.

## Legacy Group Cleanup

Older setups may contain:

- `System Status Editors`
- `Integration News Editors`
- `All News Editors`

These legacy groups are left alone by default so testing is safe until you explicitly migrate and remove them.

To copy existing users from the legacy groups into the new manager groups:

```bash
uv run python manage.py setup_groups --migrate-legacy-memberships
```

To delete the legacy groups after testing:

```bash
uv run python manage.py setup_groups --delete-legacy-groups
```

You can also do both in one run:

```bash
uv run python manage.py setup_groups --migrate-legacy-memberships --delete-legacy-groups
```

In this environment, the legacy groups have already been migrated and removed.

## Admin Notes

Use Django Admin to assign users to the new groups:

- `/admin/auth/group/`
- `/admin/auth/user/`

For a small team, this setup keeps the roles easy to reason about while still letting you test draft, publish, and review workflows separately.
