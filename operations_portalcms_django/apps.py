from django.apps import AppConfig


class OperationsPortalcmsDjangoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'operations_portalcms_django'
    verbose_name = 'Operations Portal CMS'

    def ready(self):
        """Register signal handlers when app is ready."""
        import operations_portalcms_django.signals  # noqa
