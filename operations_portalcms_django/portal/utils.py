"""
Utility functions for Operations Portal CMS
"""

def is_operations_user(user):
    """
    Check if user belongs to operations groups (concierge, badge/roadmap maintainers).

    Args:
        user: Django User object

    Returns:
        bool: True if user is in operations groups or staff
    """
    if not user or not user.is_authenticated:
        return False

    # Staff and superusers always have access
    if user.is_staff or user.is_superuser:
        return True

    # Check if user is in any operations group
    ops_groups = user.groups.filter(
        name__startswith='urn:group:access-ci.org:operations.access-ci.org:'
    )

    return ops_groups.exists()
