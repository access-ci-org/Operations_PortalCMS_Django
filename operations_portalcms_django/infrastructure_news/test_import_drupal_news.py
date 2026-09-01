import hashlib
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
from resources.models import CiderInfrastructure

from .management.commands.import_drupal_news import Command as CanonicalCommand
from .models import SystemStatusNews
from .test_drupal_mysql import _dump_text


class ImportCommandResolutionTests(SimpleTestCase):
    def test_portal_command_is_the_canonical_importer(self):
        from portal.management.commands.import_drupal_news import (
            Command as PortalCommand,
        )

        self.assertIs(PortalCommand, CanonicalCommand)


class NormalizedSourceAdjustmentTests(SimpleTestCase):
    def setUp(self):
        self.command = CanonicalCommand()
        self.records = [
            {
                "subject": "Excluded",
                "content": "",
                "start_datetime": "2023-04-03T10:00:30",
                "source_metadata": {"drupal_nid": 404},
            },
            {
                "subject": "Corrected",
                "content": "Content",
                "start_datetime": "0026-01-07T12:50:36",
                "source_metadata": {"drupal_nid": 928},
            },
        ]

    def test_excludes_and_exactly_corrects_requested_records(self):
        adjusted, exclusions, corrections = (
            self.command._adjust_normalized_system_records(
                records=self.records,
                excluded_system_nids={404},
                start_datetime_corrections={
                    928: ("0026-01-07T12:50:36", "2026-01-07T12:50:36")
                },
            )
        )

        self.assertEqual(
            [record["source_metadata"]["drupal_nid"] for record in adjusted],
            [928],
        )
        self.assertEqual(adjusted[0]["start_datetime"], "2026-01-07T12:50:36")
        self.assertEqual(exclusions, [404])
        self.assertEqual(len(corrections), 1)

    def test_refuses_correction_when_original_value_changed(self):
        self.records[1]["start_datetime"] = "2027-01-07T12:50:36"

        with self.assertRaisesMessage(CommandError, "refusing to alter"):
            self.command._adjust_normalized_system_records(
                records=self.records,
                excluded_system_nids={404},
                start_datetime_corrections={
                    928: ("0026-01-07T12:50:36", "2026-01-07T12:50:36")
                },
            )


class SystemNewsCutoffTests(SimpleTestCase):
    def setUp(self):
        self.command = CanonicalCommand()
        self.cutoff = self.command._parse_system_news_as_of(
            "2026-09-01T12:00:00Z"
        )
        self.records = [
            {
                "subject": "Past",
                "start_datetime": "2026-08-01T12:00:00Z",
                "end_datetime": "2026-08-01T13:00:00Z",
                "source_metadata": {"drupal_nid": 1},
            },
            {
                "subject": "Current",
                "start_datetime": "2026-09-01T11:00:00Z",
                "end_datetime": "2026-09-01T13:00:00Z",
                "source_metadata": {"drupal_nid": 2},
            },
            {
                "subject": "Current without end",
                "start_datetime": "2026-08-01T12:00:00Z",
                "end_datetime": None,
                "source_metadata": {"drupal_nid": 3},
            },
            {
                "subject": "Future",
                "start_datetime": "2026-09-02T12:00:00Z",
                "end_datetime": "2026-09-02T13:00:00Z",
                "source_metadata": {"drupal_nid": 4},
            },
        ]

    def test_retains_current_and_future_and_reports_past(self):
        retained, excluded = self.command._filter_system_records_as_of(
            self.records,
            self.cutoff,
        )

        self.assertEqual(
            [record["source_metadata"]["drupal_nid"] for record in retained],
            [2, 3, 4],
        )
        self.assertEqual(excluded, [1])

    def test_retains_start_or_end_exactly_at_cutoff(self):
        records = [
            {
                "start_datetime": "2026-09-01T12:00:00Z",
                "end_datetime": "2026-09-01T13:00:00Z",
                "source_metadata": {"drupal_nid": 10},
            },
            {
                "start_datetime": "2026-09-01T11:00:00Z",
                "end_datetime": "2026-09-01T12:00:00Z",
                "source_metadata": {"drupal_nid": 11},
            },
        ]

        retained, excluded = self.command._filter_system_records_as_of(
            records,
            self.cutoff,
        )

        self.assertEqual(len(retained), 2)
        self.assertEqual(excluded, [])

    def test_allows_no_retained_system_records(self):
        retained, excluded = self.command._filter_system_records_as_of(
            [self.records[0]],
            self.cutoff,
        )

        self.assertEqual(retained, [])
        self.assertEqual(excluded, [1])
        self.assertEqual(
            self.command._validated_source_ids(
                retained,
                "SystemStatusNews",
                allow_empty=True,
            ),
            set(),
        )

    def test_rejects_naive_cutoff(self):
        with self.assertRaisesMessage(CommandError, "timezone-aware ISO-8601"):
            self.command._parse_system_news_as_of("2026-09-01T12:00:00")

    def test_rejects_record_without_valid_start(self):
        with self.assertRaisesMessage(CommandError, "valid start_datetime"):
            self.command._filter_system_records_as_of(
                [
                    {
                        "start_datetime": "not-a-date",
                        "source_metadata": {"drupal_nid": 12},
                    }
                ],
                self.cutoff,
            )


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
        source_confirmation = []
        if "--apply" in mode:
            source_confirmation = [
                "--confirm-source-sha256",
                hashlib.sha256(self.input_path.read_bytes()).hexdigest(),
                "--confirm-system-count",
                "1",
                "--confirm-integration-count",
                "1",
            ]
        return call_command(
            "import_drupal_news",
            "--input",
            str(self.input_path),
            "--report-file",
            str(self.report_path),
            "--import-user",
            self.author.username,
            "--replace",
            "--system-news-as-of",
            "2026-01-01T00:00:00Z",
            "--confirm-database",
            self.database_name,
            "--confirm-host",
            self.database_host,
            "--suppress-notifications",
            *source_confirmation,
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

    def test_replace_apply_preserves_multiple_integration_elements(self):
        payload = self._payload()
        payload["IntegrationNews"][0]["affected_elements"] = ["nagios", "cider"]
        payload["IntegrationNews"][0]["affected_element"] = ""
        self._write_payload(payload)

        self._run_replace("--apply")

        integration = IntegrationNews.objects.get(integration_news_id=201)
        self.assertEqual(
            set(integration.affected_elements.values_list("code", flat=True)),
            {"nagios", "cider"},
        )

    def test_replace_apply_requires_matching_source_checksum(self):
        self._write_payload()

        with self.assertRaisesMessage(CommandError, "source SHA-256 does not match"):
            call_command(
                "import_drupal_news",
                "--input",
                str(self.input_path),
                "--replace",
                "--system-news-as-of",
                "2026-01-01T00:00:00Z",
                "--apply",
                "--confirm-database",
                self.database_name,
                "--confirm-host",
                self.database_host,
                "--confirm-source-sha256",
                "0" * 64,
                "--confirm-system-count",
                "1",
                "--confirm-integration-count",
                "1",
                stdout=StringIO(),
            )

    def test_raw_dump_apply_replaces_both_feeds_with_all_relationships(self):
        raw_path = Path(self.temp_dir.name) / "news.mysql"
        raw_path.write_text(_dump_text(), encoding="utf-8")
        CiderInfrastructure.objects.create(
            cider_resource_id=301,
            cider_type="compute",
            info_resourceid="resource.example",
            info_siteid="example",
            resource_descriptive_name="Example resource",
        )

        call_command(
            "import_drupal_news",
            "--mysql-dump",
            str(raw_path),
            "--replace",
            "--system-news-as-of",
            "2026-01-01T00:00:00Z",
            "--apply",
            "--strict",
            "--confirm-database",
            self.database_name,
            "--confirm-host",
            self.database_host,
            "--confirm-source-sha256",
            hashlib.sha256(raw_path.read_bytes()).hexdigest(),
            "--confirm-system-count",
            "1",
            "--confirm-integration-count",
            "1",
            "--suppress-notifications",
            "--report-file",
            str(self.report_path),
            "--import-user",
            self.author.username,
            stdout=StringIO(),
        )

        system = SystemStatusNews.objects.get(outage_id=101)
        integration = IntegrationNews.objects.get(integration_news_id=201)
        self.assertEqual(
            set(
                system.affected_infrastructure_items.values_list(
                    "info_resourceid", flat=True
                )
            ),
            {"resource.example"},
        )
        self.assertEqual(
            set(integration.affected_elements.values_list("code", flat=True)),
            {"compute_roadmap", "accessusage"},
        )
        self.assertFalse(system.send_email)
        self.assertFalse(system.post_to_slack)

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
                "--system-news-as-of",
                "2026-01-01T00:00:00Z",
                "--dry-run",
                "--confirm-database",
                self.database_name,
                "--confirm-host",
                "not-the-configured-host",
                stdout=StringIO(),
            )

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(IntegrationNews.objects.filter(pk=self.old_integration.pk).exists())
