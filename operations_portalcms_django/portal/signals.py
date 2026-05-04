"""
CILogon post-login signal handlers for Operations Portal CMS.

Replicates functionality from Service Index to ensure consistent behavior:
1. set_username() - Extract username from CILogon 'sub' claim
2. logout_log() - Audit log logout events
3. connect_existing_user() - Link new CILogon logins to existing users by email
"""

import logging
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_logged_out
from django.contrib.auth.models import Group
from allauth.socialaccount.signals import pre_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from allauth.account.utils import setup_user_email

logger = logging.getLogger(__name__)


def sync_cilogon_groups(user, sociallogin):
    """
    Sync user's Django groups from CILogon group memberships.
    
    CILogon returns group memberships in the 'isMemberOf' claim as URNs:
    Example: ['urn:group:access-ci.org:rp.access-ci.org:coordinator', ...]
    
    This function:
    1. Extracts group URNs from CILogon claims
    2. Matches them to Django groups created by setup_rp_permissions
    3. Adds user to matching groups
    4. Removes user from groups they no longer belong to
    
    Args:
        user: Django User object
        sociallogin: SocialAccount object with CILogon data
    """
    try:
        # Get group memberships from CILogon claims
        cilogon_groups = sociallogin.extra_data.get('isMemberOf', [])
        
        if not isinstance(cilogon_groups, list):
            cilogon_groups = [cilogon_groups] if cilogon_groups else []
        
        logger.info(f"CILogon groups for {user.username}: {len(cilogon_groups)} groups")
        
        # Filter to only ACCESS-CI groups (RP groups)
        access_groups = [
            g for g in cilogon_groups 
            if g.startswith('urn:group:access-ci.org:')
        ]
        
        if not access_groups:
            logger.info(f"No ACCESS-CI groups found for {user.username}")
            # Remove user from all RP groups if they no longer have membership
            current_groups = user.groups.filter(name__startswith='urn:group:access-ci.org:')
            if current_groups.exists():
                user.groups.remove(*current_groups)
                logger.info(f"Removed {user.username} from {current_groups.count()} RP groups")
            return
        
        # Get existing Django groups that match the CILogon URNs
        matching_groups = Group.objects.filter(name__in=access_groups)
        
        # Current groups the user is in (RP groups only)
        current_rp_groups = set(
            user.groups.filter(name__startswith='urn:group:access-ci.org:')
            .values_list('name', flat=True)
        )
        
        # Groups from CILogon
        cilogon_group_set = set(access_groups)
        
        # Groups to add (in CILogon but not in Django user.groups)
        groups_to_add = cilogon_group_set - current_rp_groups
        
        # Groups to remove (in Django user.groups but not in CILogon)
        groups_to_remove = current_rp_groups - cilogon_group_set
        
        # Add user to new groups
        if groups_to_add:
            new_groups = Group.objects.filter(name__in=groups_to_add)
            if new_groups.exists():
                user.groups.add(*new_groups)
                logger.info(f"Added {user.username} to {new_groups.count()} groups: {list(groups_to_add)}")
        
        # Remove user from old groups
        if groups_to_remove:
            old_groups = Group.objects.filter(name__in=groups_to_remove)
            if old_groups.exists():
                user.groups.remove(*old_groups)
                logger.info(f"Removed {user.username} from {old_groups.count()} groups: {list(groups_to_remove)}")
        
        # Log final group count
        final_count = user.groups.filter(name__startswith='urn:group:access-ci.org:').count()
        logger.info(f"User {user.username} now has {final_count} RP groups")
        
    except Exception as e:
        logger.error(f"Error syncing CILogon groups for {user.username}: {e}", exc_info=True)


@receiver(user_logged_in)
def set_username(sender, request, user, **kwargs):
    """
    Extract username from CILogon 'sub' claim and set it on the user.
    
    CILogon returns subject as: username@institution.org
    We extract the username part and validate it exists.
    
    Args:
        sender: The User model
        request: The current request
        user: The logged-in user
    """
    try:
        # Get the CILogon social account for this user
        sociallogin = user.socialaccount_set.filter(provider='cilogon').first()
        if not sociallogin:
            logger.warning(f"CILogon account not found for user {user.id}")
            return
            
    except Exception as e:
        logger.error(f"Error fetching CILogon account for user {user.id}: {e}")
        return

    # Extract subject from extra_data
    subject = sociallogin.extra_data.get('sub', '')
    if not subject:
        logger.warning(f"CILogon 'sub' claim missing for user {user.id}")
        return

    # Parse username from subject (format: username@institution.org)
    try:
        username = subject.split('@')[0]
        if not username:
            logger.warning(f"Invalid CILogon subject format for user {user.id}: {subject}")
            return
    except Exception as e:
        logger.error(f"Error parsing CILogon subject for user {user.id}: {e}")
        return

    # Update username if different
    if user.username != username:
        user.username = username
        user.save()
        logger.info(f"Updated username for CILogon user {subject} -> {username}")

    # Sync user's groups from CILogon claims
    sync_cilogon_groups(user, sociallogin)

    # Log the login with IP
    remote_ip = request.META.get('HTTP_X_FORWARDED_FOR')
    if not remote_ip:
        remote_ip = request.META.get('REMOTE_ADDR')
    
    logger.info(f"CILogon login: {subject} as {user.username} from {remote_ip}")


@receiver(user_logged_out)
def logout_log(sender, request, user, **kwargs):
    """
    Audit log user logout events.
    
    Args:
        sender: The User model
        request: The current request
        user: The logged-out user
    """
    username = getattr(user, 'username', 'unknown')
    logger.info(f"User logout: {username}")


@receiver(pre_social_login)
def connect_existing_user(sender, request, sociallogin, **kwargs):
    """
    Connect new CILogon login to existing Django user by email.
    
    If a user logs in with CILogon for the first time but an existing user
    account has the same email, link them together instead of creating a duplicate.
    
    This prevents duplicate accounts when a user already has a local account
    and then authenticates via CILogon.
    
    Args:
        sender: The signal sender
        request: The current request
        sociallogin: The SocialLogin object
    """
    # Skip if user already exists (not a new login)
    if sociallogin.is_existing:
        return

    # Try to find email in the CILogon response
    try:
        if not sociallogin.email_addresses:
            logger.warning("CILogon login missing email addresses")
            return
        email = sociallogin.email_addresses[0].email
    except (IndexError, AttributeError):
        logger.warning("Could not extract email from CILogon response")
        return

    # Try to find existing user by email
    try:
        existing_user = User.objects.get(email=email)
    except User.DoesNotExist:
        # No existing user, let Allauth create a new one
        logger.info(f"New CILogon user with email {email}")
        return
    except User.MultipleObjectsReturned:
        logger.warning(f"Multiple users found with email {email}, cannot auto-link")
        return

    # Link the CILogon account to the existing user
    try:
        sociallogin.connect(request, existing_user)
        setup_user_email(request, existing_user, [])
        logger.info(f"CILogon account linked to existing user {existing_user.username} (email: {email})")
    except Exception as e:
        logger.error(f"Error linking CILogon account to existing user {existing_user.username}: {e}")
