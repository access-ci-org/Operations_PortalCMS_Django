from unittest.mock import MagicMock, patch

from django.db.utils import InterfaceError, OperationalError
from django.test import SimpleTestCase, override_settings
from django.urls import reverse


@override_settings(APP_VERSION='v-test')
class ReadinessTests(SimpleTestCase):
    @patch('portal.health.connection.cursor')
    def test_readiness_reports_version_when_database_is_available(self, cursor):
        cursor.return_value.__enter__.return_value = MagicMock()

        response = self.client.get(reverse('portal:healthz'))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {'status': 'ok', 'version': 'v-test'})

    @patch('portal.health.connection.cursor', side_effect=OperationalError)
    def test_readiness_reports_unavailable_without_error_details(self, cursor):
        response = self.client.get(reverse('portal:healthz'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {'status': 'unavailable', 'version': 'v-test'},
        )

    @patch('portal.health.connection.cursor', side_effect=InterfaceError)
    def test_readiness_handles_database_interface_failures(self, cursor):
        response = self.client.get(reverse('portal:healthz'))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {'status': 'unavailable', 'version': 'v-test'},
        )
