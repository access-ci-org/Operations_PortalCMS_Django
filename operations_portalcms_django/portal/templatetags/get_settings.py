"""
Template tags for getting Django settings values in templates.
Used by access_django_user_admin app.
"""
from django import template
from django.conf import settings

register = template.Library()

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEVELOPMENT_ENVS = {"dev", "development", "local"}


def _hostname_without_port(hostname):
    hostname = (hostname or "").strip().lower()
    if hostname.startswith("[") and "]" in hostname:
        return hostname[1:hostname.index("]")]
    if hostname.count(":") == 1:
        return hostname.split(":", 1)[0]
    return hostname


def _is_local_hostname(hostname):
    return _hostname_without_port(hostname) in LOCAL_HOSTS


def _database_name():
    return settings.DATABASES.get("default", {}).get("NAME", "")


def _forced_development_banner(request):
    app_env = getattr(settings, "APP_ENV", "").strip().lower()
    public_hostname = getattr(settings, "PUBLIC_HOSTNAME", "")
    request_hostname = request.get_host() if request else ""

    return (
        _database_name() == "portal_dev"
        or app_env in DEVELOPMENT_ENVS
        or _is_local_hostname(public_hostname)
        or _is_local_hostname(request_hostname)
    )


def _environment_banner_context(request=None):
    if _forced_development_banner(request):
        return {
            "enabled": True,
            "label": "DEVELOPMENT",
        }

    return {
        "enabled": bool(getattr(settings, "DEVELOPMENT_SERVER_BANNER", False)),
        "label": getattr(settings, "DEVELOPMENT_SERVER_LABEL", ""),
    }


@register.simple_tag
def settings_value(name):
    """
    Get a setting value from Django settings.
    Usage: {% settings_value 'SETTING_NAME' %}
    """
    return getattr(settings, name, "")


@register.simple_tag(takes_context=True)
def environment_banner(context):
    """
    Return the effective environment banner for the current request.
    """
    return _environment_banner_context(context.get("request"))


@register.filter
def can_admin_users(user):
    """
    Check if user has permission to administer users.
    Usage: {% if user|can_admin_users %}
    """
    return (user.is_superuser or
            user.has_perm('auth.add_user') or
            user.groups.filter(name='account-admins').exists())
