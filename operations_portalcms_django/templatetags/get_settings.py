"""
Template tags for getting Django settings values in templates.
Used by access_django_user_admin app.
"""
from django import template
from django.conf import settings

register = template.Library()


@register.simple_tag
def settings_value(name):
    """
    Get a setting value from Django settings.
    Usage: {% settings_value 'SETTING_NAME' %}
    """
    return getattr(settings, name, "")


@register.filter
def can_admin_users(user):
    """
    Check if user has permission to administer users.
    Usage: {% if user|can_admin_users %}
    """
    return (user.is_superuser or
            user.has_perm('auth.add_user') or
            user.groups.filter(name='account-admins').exists())
