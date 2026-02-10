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
from allauth.socialaccount.signals import pre_social_login
from allauth.socialaccount.models import SocialAccount
from django.contrib.auth.models import User
from allauth.account.utils import setup_user_email

logger = logging.getLogger(__name__)


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
