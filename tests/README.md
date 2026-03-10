# Integration Tests

Integration tests for the Operations Portal CMS Resource Provider permission system.

## Running Tests

Run individual test files:
```bash
uv run python tests/test_permissions.py
uv run python tests/test_news_permissions.py
```

Run all tests with pytest (if installed):
```bash
uv run pytest tests/
```

## Test Coverage

### test_permissions.py
Tests CILogon group synchronization:
- RP coordinator permissions
- RP implementer permissions  
- Multiple RP memberships
- Group membership changes on re-login

### test_news_permissions.py
Tests news admin permissions:
- Helper utility functions
- Admin add/change/delete permissions
- News item creation by RP users
- Multiple RP group memberships

## Expected Output

Both test scripts will print detailed output showing:
- Test scenarios being executed
- Group assignments
- Permission checks
- Success/failure indicators

All tests should pass with `✓ ALL TESTS PASSED` message.
