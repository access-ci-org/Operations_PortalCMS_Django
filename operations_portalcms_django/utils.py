"""
Utility functions for Operations Portal CMS
"""
from django.contrib.auth.models import User


def is_rp_user(user):
    """
    Check if user belongs to any Resource Provider group.
    
    Returns True if user is in any RP coordinator or implementer group,
    or if they're staff/superuser.
    
    Args:
        user: Django User object
        
    Returns:
        bool: True if user is RP member or staff, False otherwise
    """
    if not user or not user.is_authenticated:
        return False
    
    # Staff and superusers always have access
    if user.is_staff or user.is_superuser:
        return True
    
    # Check if user is in any RP group (coordinator or implementer)
    rp_groups = user.groups.filter(
        name__startswith='urn:group:access-ci.org:rp.'
    )
    
    return rp_groups.exists()


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


def get_user_rp_groups(user):
    """
    Get list of RP group IDs (info_groupid) that user belongs to.
    
    Example return: ['rp.psc.edu', 'rp.tacc.utexas.edu']
    
    Args:
        user: Django User object
        
    Returns:
        list: List of RP group IDs (strings)
    """
    if not user or not user.is_authenticated:
        return []
    
    rp_groups = user.groups.filter(
        name__startswith='urn:group:access-ci.org:rp.'
    )
    
    # Extract the group ID from URN format
    # Example: urn:group:access-ci.org:rp.psc.edu:coordinator -> rp.psc.edu
    group_ids = []
    for group in rp_groups:
        parts = group.name.split(':')
        if len(parts) >= 4:
            # parts[3] is the RP group ID
            group_id = parts[3]
            if group_id not in group_ids:
                group_ids.append(group_id)
    
    return group_ids


def is_rp_coordinator(user):
    """
    Check if user is a coordinator for any RP.
    
    Args:
        user: Django User object
        
    Returns:
        bool: True if user is coordinator for any RP
    """
    if not user or not user.is_authenticated:
        return False
    
    if user.is_staff or user.is_superuser:
        return True
    
    coordinator_groups = user.groups.filter(
        name__startswith='urn:group:access-ci.org:rp.',
        name__endswith=':coordinator'
    )
    
    return coordinator_groups.exists()


def can_manage_news(user):
    """
    Check if user can add/edit news items.
    
    Users who can manage news:
    - RP coordinators or implementers
    - Operations staff (concierge, maintainers)
    - Django staff/superusers
    
    Args:
        user: Django User object
        
    Returns:
        bool: True if user can manage news
    """
    return is_rp_user(user) or is_operations_user(user)
