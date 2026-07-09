from types import SimpleNamespace
from unittest import TestCase, mock

from portal.templatetags import get_settings


class EnvironmentBannerTests(TestCase):
    def banner(self, *, app_env="", public_hostname="", request_host="", db_name="portal1",
               banner_enabled=False, banner_label=""):
        request = SimpleNamespace(get_host=lambda: request_host)
        database_settings = {"default": {"NAME": db_name}}

        with mock.patch.object(get_settings.settings, "APP_ENV", app_env, create=True), \
             mock.patch.object(get_settings.settings, "PUBLIC_HOSTNAME", public_hostname, create=True), \
             mock.patch.object(get_settings.settings, "DATABASES", database_settings, create=True), \
             mock.patch.object(get_settings.settings, "DEVELOPMENT_SERVER_BANNER", banner_enabled, create=True), \
             mock.patch.object(get_settings.settings, "DEVELOPMENT_SERVER_LABEL", banner_label, create=True):
            return get_settings._environment_banner_context(request)

    def test_explicit_beta_banner(self):
        banner = self.banner(
            app_env="beta",
            public_hostname="beta-operations.access-ci.org",
            banner_enabled=True,
            banner_label="BETA SERVER",
        )

        self.assertEqual(banner, {"enabled": True, "label": "BETA SERVER"})

    def test_explicit_development_environment_forces_development(self):
        banner = self.banner(app_env="development", banner_enabled=True, banner_label="BETA SERVER")

        self.assertEqual(banner, {"enabled": True, "label": "DEVELOPMENT"})

    def test_portal_dev_database_forces_development(self):
        banner = self.banner(app_env="production", db_name="portal_dev", banner_enabled=False)

        self.assertEqual(banner, {"enabled": True, "label": "DEVELOPMENT"})

    def test_localhost_request_forces_development(self):
        banner = self.banner(app_env="production", request_host="localhost:8000", banner_enabled=False)

        self.assertEqual(banner, {"enabled": True, "label": "DEVELOPMENT"})

    def test_production_portal1_has_no_banner(self):
        banner = self.banner(
            app_env="production",
            public_hostname="operations.access-ci.org",
            db_name="portal1",
            banner_enabled=False,
        )

        self.assertEqual(banner, {"enabled": False, "label": ""})
