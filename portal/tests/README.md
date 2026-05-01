# Integration Check Scripts

Standalone integration/check scripts for the Operations Portal CMS permission and workflow systems.

## Important Safety Note

These are not isolated Django `TestCase` tests. They call `django.setup()` and operate on whichever database is selected by `APP_CONFIG` and environment variables.

Do not run them against the database of record, RDS `portal1`, unless you explicitly intend to create or modify test users, groups, and content there. Prefer a disposable clone or local test database.

## Running Tests

Run individual scripts against an explicitly selected non-production config:

```bash
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_permissions.py
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_news_permissions.py
APP_CONFIG=/path/to/non-production-config.json uv run python tests/test_focus_area_page_workflow.py
```

There is no pytest configuration in this repo right now, and `pytest` is not listed in `pyproject.toml`.

## Test Coverage

### test_permissions.py
Tests CILogon group synchronization:
- RP coordinator permissions
- RP implementer permissions  
- Multiple RP memberships
- Group membership changes on re-login

Side effects: creates or updates users such as `psc_coordinator`, `multi_role_user`, and `former_coordinator`, and changes group memberships. It does not clean all of those users up.

### test_news_permissions.py
Tests news admin permissions:
- Helper utility functions
- Admin add/change/delete permissions
- News item creation by RP users
- Multiple RP group memberships

Side effects: creates temporary `test_*` users, groups, and news items. It cleans up `test_*` users at the end when successful.

### test_focus_area_page_workflow.py
Tests focus-area page permissions:
- STEP page editor can change but not publish
- `Focus_area_editors` can change and publish
- PagePermission records are effective for the STEP page

Side effects: creates or updates `test_step_page_editor` and `test_general_focus_editor`, sets them staff, clears their groups, and assigns focus-area groups. It does not remove those users.

## Expected Output

The scripts print detailed output showing:
- Test scenarios being executed
- Group assignments
- Permission checks
- Success/failure indicators

Successful runs end with `ALL TESTS PASSED` or `✓ ALL TESTS PASSED`.

## Read-Only Verification Alternatives

For the current database of record, use read-only checks instead:

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json \
APP_LOG=/tmp/portal-check.log \
APP_ERROR_LOG=/tmp/portal-check.error.log \
uv run python manage.py check
```

```bash
APP_CONFIG=/soft/django-cms-01/conf/portal.conf.dev.json ./database/verify_db.sh
```

See [CURRENT_STATE.md](../READMEs/CURRENT_STATE.md) for the latest verified counts and command results.
