from django.apps import AppConfig


class OperationsPortalcmsDjangoConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'portal'
    verbose_name = 'Operations Portal CMS'

    def ready(self):
        """Register signal handlers when app is ready."""
        import portal.signals  # noqa
        import portal.cms_toolbars  # noqa
