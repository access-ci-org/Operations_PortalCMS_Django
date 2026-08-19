import json
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase

from integration_news.models import IntegrationNews

from .management.commands.import_drupal_news import Command as CanonicalCommand
from .models import SystemStatusNews


class ImportCommandResolutionTests(SimpleTestCase):
    def test_portal_command_is_the_canonical_importer(self):
        from portal.management.commands.import_drupal_news import Command as PortalCommand

        self.assertIs(PortalCommand, CanonicalCommand)


class AtomicReplaceCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.input_path = Path(self.temp_dir.name) / "news.json"
        self.report_path = Path(self.temp_dir.name) / "report.md"
        self.author = User.objects.create_user(username="cutover_author")
        self.old_system = SystemStatusNews.objects.create(
            subject="Old system news",
            content="Old content",
            infrastructure_news_type="degraded",
            outage_id=1,
            author=self.author,
        )
        self.old_integration = IntegrationNews.objects.create(
            title="Old integration news",
            content="Old content",
            news_type="software_release",
            integration_news_id=2,
            author=self.author,
        )
        configured = settings.DATABASES["default"]
        self.database_name = str(configured.get("NAME") or "")
        self.database_host = str(configured.get("HOST") or "")

    def _payload(self):
        return {
            "SystemStatusNews": [
                {
                    "subject": "Imported system news",
                    "content": "Imported system content",
                    "infrastructure_news_type": "outage_partial",
                    "affected_infrastructure": "",
                    "start_datetime": "2026-08-01T12:00:00Z",
                    "end_datetime": "2026-08-01T13:00:00Z",
                    "send_email": True,
                    "post_to_slack": True,
                    "is_active": True,
                    "status": "published",
                    "source_metadata": {
                        "drupal_nid": 101,
                        "drupal_vid": 1001,
                        "drupal_created_at": "2026-08-01T11:00:00Z",
                    },
                }
            ],
            "IntegrationNews": [
                {
                    "title": "Imported integration news",
                    "content": "Imported integration content",
                    "news_type": "software_release",
                    "affected_element": "nagios",
                    "effective_date": "2026-08-01",
                    "expiration_date": "2026-09-01",
                    "is_active": True,
                    "status": "published",
                    "source_metadata": {
                        "drupal_nid": 201,
                        "drupal_vid": 2001,
                        "drupal_created_at": "2026-08-01T11:00:00Z",
                    },
                }
            ],
        }

    def _write_payload(self, payload=None):
        self.input_path.write_text(
            json.dumps(payload or self._payload()),
            encoding="utf-8",
        )

    def _run_replace(self, *mode):
        return call_command(
            "import_drupal_news",
            "--input",
            str(self.input_path),
            "--report-file",
            str(self.report_path),
            "--import-user",
            self.author.username,
            "--replace",
            "--confirm-database",
            self.database_name,
            "--confirm-host",
            self.database_host,
            "--suppress-notifications",
            *mode,
            stdout=StringIO(),
        )

    def test_replace_dry_run_preserves_rows_and_reports_plan(self):
        self._write_payload()

        self._run_replace("--dry-run")

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(IntegrationNews.objects.filter(pk=self.old_integration.pk).exists())
        self.assertFalse(SystemStatusNews.objects.filter(outage_id=101).exists())
        self.assertFalse(IntegrationNews.objects.filter(integration_news_id=201).exists())
        report = self.report_path.read_text(encoding="utf-8")
        self.assertIn("`SystemStatusNews` deleted: `1`", report)
        self.assertIn("`IntegrationNews` deleted: `1`", report)
        self.assertIn("`SystemStatusNews` created: `1`", report)
        self.assertIn("`IntegrationNews` created: `1`", report)

    def test_replace_apply_replaces_both_feeds_and_builds_relationships(self):
        self._write_payload()

        self._run_replace("--apply")

        self.assertEqual(SystemStatusNews.objects.count(), 1)
        self.assertEqual(IntegrationNews.objects.count(), 1)
        system = SystemStatusNews.objects.get(outage_id=101)
        integration = IntegrationNews.objects.get(integration_news_id=201)
        self.assertFalse(system.send_email)
        self.assertFalse(system.post_to_slack)
        self.assertEqual(
            list(integration.affected_elements.values_list("code", flat=True)),
            ["nagios"],
        )

    def test_replace_rolls_back_deletion_and_import_on_final_validation_failure(self):
        self._write_payload()

        with patch.object(
            CanonicalCommand,
            "_validate_replacement",
            side_effect=CommandError("forced validation failure"),
        ):
            with self.assertRaisesMessage(CommandError, "forced validation failure"):
                self._run_replace("--apply")

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(IntegrationNews.objects.filter(pk=self.old_integration.pk).exists())
        self.assertFalse(SystemStatusNews.objects.filter(outage_id=101).exists())
        self.assertFalse(IntegrationNews.objects.filter(integration_news_id=201).exists())

    def test_replace_rejects_duplicate_source_ids_before_deleting(self):
        payload = self._payload()
        payload["SystemStatusNews"].append(dict(payload["SystemStatusNews"][0]))
        self._write_payload(payload)

        with self.assertRaisesMessage(CommandError, "duplicate Drupal nid 101"):
            self._run_replace("--apply")

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(IntegrationNews.objects.filter(pk=self.old_integration.pk).exists())

    def test_replace_rejects_unconfirmed_target(self):
        self._write_payload()

        with self.assertRaisesMessage(CommandError, "configured write host does not match"):
            call_command(
                "import_drupal_news",
                "--input",
                str(self.input_path),
                "--replace",
                "--dry-run",
                "--confirm-database",
                self.database_name,
                "--confirm-host",
                "not-the-configured-host",
                stdout=StringIO(),
            )

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(IntegrationNews.objects.filter(pk=self.old_integration.pk).exists())
