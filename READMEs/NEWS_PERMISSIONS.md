# News Admin Permissions - Implementation Summary

## What Was Implemented

A simple, flexible permission system where **any RP user can add/edit news items**.

## The Simple Rule

✅ **If you're in ANY RP group** (coordinator or implementer), you can add/edit news  
✅ **No infrastructure matching required** - encourages cross-RP collaboration  

## How It Works

### 1. User Logs In via CILogon
- User authenticates with CILogon
- `sync_cilogon_groups()` adds them to RP groups automatically
- Example: Added to `urn:group:access-ci.org:rp.psc.edu:coordinator`

### 2. User Access Django Admin
- Navigates to `/admin/`
- Sees **System Status News** and **Integration News** sections
- Can click "Add" button

### 3. Permissions Check
```python
# When user clicks "Add System Status News"
def has_add_permission(request):
    # Is user in ANY RP group?
    if user.groups.filter(name__startswith='urn:group:access-ci.org:rp.').exists():
        return True  # ✓ Allow access
    return False
```

### 4. User Creates News
- Fills out form with infrastructure details
- Can specify any infrastructure (not limited to their RP)
- Submits and saves

### 5. User Can Edit/Delete Own Items
- Can always edit news they authored
- Can delete their own items
- Can see all news items (to stay informed)

## Permission Matrix

| User Type | Add News | Edit Own | Edit Others | Delete Own | Delete Others | View All |
|-----------|----------|----------|-------------|------------|---------------|----------|
| **RP Coordinator** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **RP Implementer** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Operations (concierge)** | ✅ | ✅ | ✅ | ✅ | ❌ | ✅ |
| **Staff/Superuser** | ✅ | ✅ | ✅ | ✅ | ✅ | ✅ |
| **Regular User** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

## Files Modified

### 1. `operations_portalcms_django/utils.py` (NEW)
Utility functions:
- `is_rp_user(user)` - Check if in any RP group
- `is_operations_user(user)` - Check if in operations groups
- `can_manage_news(user)` - Check if can add/edit news
- `get_user_rp_groups(user)` - Get list of RP IDs user belongs to
- `is_rp_coordinator(user)` - Check if user is coordinator

### 2. `operations_portalcms_django/admin.py`
Updated both admin classes:

**SystemStatusNewsAdmin:**
- `has_add_permission()` - RP users can add
- `has_change_permission()` - Authors + RP users can edit
- `has_delete_permission()` - Authors + staff can delete
- Made `author` readonly (auto-set on save)

**IntegrationNewsAdmin:**
- Same permission logic as SystemStatusNews
- Simple, consistent approach

### 3. `test_news_permissions.py` (NEW)
Comprehensive test suite verifying:
- Helper functions work correctly
- Admin permissions enforce rules
- RP users can create/edit news
- Multiple RP memberships handled
- Regular users blocked

## Why This Approach?

**✅ Advantages:**
1. **Simple** - Easy to understand and maintain
2. **Collaborative** - PSC can report on TACC infrastructure if needed
3. **Flexible** - No rigid resource ownership constraints
4. **Automatic** - Permissions sync from CILogon
5. **Secure** - Regular users can't access admin

**❌ No Restrictions On:**
- Which infrastructure IDs can be entered
- Cross-RP news reporting
- Viewing other RPs' news items

**This is intentional** - RPs need to see all infrastructure news for coordination.

## Real-World Example

**Scenario:** Power outage affects multiple sites

1. **PSC coordinator logs in** (via CILogon)
2. **Automatically gets RP coordinator permissions**
3. **Creates System Status News:**
   - Subject: "Power Outage - Multiple Sites"
   - Affected Infrastructure: `bridges2.psc.edu, stampede3.tacc.utexas.edu`
   - Type: Outage - Partial
4. **TACC implementer logs in**
5. **Sees PSC's news item** in the list
6. **Can add their own updates** about TACC status
7. **Both can collaborate** on cross-site issues

## Testing

Run the test suite anytime:
```bash
uv run python test_news_permissions.py
```

All tests pass ✅

## Admin UI Experience

**For RP Users:**
1. Log into `/admin/`
2. See sections:
   - **OPERATIONS_PORTALCMS_DJANGO**
     - System and Infrastructure Status News → Can Add ✅
     - Integration News → Can Add ✅
3. Click "Add" → Fill out form → Save
4. See own items in list with Edit/Delete buttons
5. See others' items in list (read-only unless staff)

**For Regular Users:**
- Don't see news sections at all
- Blocked from accessing `/admin/operations_portalcms_django/systemstatusnews/`

## Future Enhancements (Optional)

If you later want to add restrictions:

1. **Filter infrastructure dropdown** - Show only user's RP resources
2. **Validate infrastructure field** - Check against RP ownership
3. **Change to ManyToManyField** - More structured than CharField
4. **Add approval workflow** - Coordinators approve implementer posts
5. **Email notifications** - Alert RP when news added

But for now, **keep it simple** - trust your RP users to report accurately.

## Summary

✅ **Implemented:** Simple RP-based news permissions  
✅ **Tested:** All tests passing  
✅ **Ready:** For production use  

**Key Feature:** Any RP member can add news about any infrastructure - encourages collaboration and information sharing across Resource Providers.
