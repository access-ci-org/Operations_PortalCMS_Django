import hashlib
import json
import os
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth.models import User
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import SimpleTestCase, TestCase
from django.utils.dateparse import parse_datetime
from integration_news.models import IntegrationNews
from resources.models import CiderInfrastructure

from .management.commands.import_drupal_news import Command as CanonicalCommand
from .management.commands.import_drupal_news import ImportResult
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


class MysqlDumpSelectionTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)
        self.command = CanonicalCommand()

    def test_selects_newest_filename_timestamp_not_mtime(self):
        older = self.directory / "backup_database-2026-08-31T04:00:03-05:00.mysql.gz"
        newer = self.directory / "backup_database-2026-09-01T04:00:03-05:00.mysql.gz"
        older.write_bytes(b"older")
        newer.write_bytes(b"newer")
        os.utime(older, (2_000_000_000, 2_000_000_000))
        os.utime(newer, (1_000_000_000, 1_000_000_000))

        selected = self.command._select_newest_mysql_dump(self.directory)

        self.assertEqual(selected, newer.resolve())

    def test_rejects_malformed_matching_backup_filename(self):
        malformed = self.directory / "backup_database-not-a-date.mysql.gz"
        malformed.write_bytes(b"data")

        with self.assertRaisesMessage(CommandError, "Malformed MySQL backup filename"):
            self.command._select_newest_mysql_dump(self.directory)

    def test_rejects_two_names_for_same_newest_instant(self):
        first = self.directory / "backup_database-2026-09-01T04:00:03-05:00.mysql.gz"
        second = self.directory / "backup_database-2026-09-01T09:00:03Z.mysql.gz"
        first.write_bytes(b"first")
        second.write_bytes(b"second")

        with self.assertRaisesMessage(CommandError, "same newest instant"):
            self.command._select_newest_mysql_dump(self.directory)


class ImportPlanTests(SimpleTestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.directory = Path(self.temp_dir.name)
        self.source_path = self.directory / "news.json"
        self.source_path.write_text("{}", encoding="utf-8")
        self.plan_path = self.directory / "import-plan.json"
        self.command = CanonicalCommand()
        self.result = ImportResult(
            system_records=1,
            integration_records=1,
            system_relationships=2,
            integration_relationships=1,
            excluded_system_nids=[404],
            cutoff_excluded_system_nids=[1, 2],
            system_news_as_of="2026-09-01T12:00:00Z",
            source_corrections=["correction applied"],
            system_attribution=[
                {
                    "nid": 101,
                    "drupal_uid": 11,
                    "drupal_username": "source_author",
                    "django_username": "source_author",
                    "resolution": "drupal-username",
                    "fallback_reason": "",
                    "posted_at": "2026-08-01T11:00:00+00:00",
                }
            ],
            integration_attribution=[
                {
                    "nid": 201,
                    "drupal_uid": 12,
                    "drupal_username": "missing_author",
                    "django_username": "cutover_author",
                    "resolution": "fallback",
                    "fallback_reason": "no-django-username-match",
                    "posted_at": "2026-08-01T11:00:00+00:00",
                }
            ],
            created_system=1,
            created_integration=1,
            deleted_system=3,
            deleted_integration=4,
        )
        self.options = {
            "suppress_notifications": True,
            "allow_na_affected_element": True,
            "create_import_user": False,
            "import_user": "cutover_author",
        }

    def _plan(self):
        return self.command._build_import_plan(
            input_path=self.source_path,
            source_kind="normalized-json",
            source_sha256=hashlib.sha256(self.source_path.read_bytes()).hexdigest(),
            result=self.result,
            expected_system_ids={101},
            expected_integration_ids={201},
            excluded_system_nids=[404],
            source_correction_names=["infrastructure-928-start-year"],
            options=self.options,
        )

    def test_round_trips_versioned_plan_and_file_digest(self):
        plan = self._plan()
        plan_sha256 = self.command._write_import_plan(self.plan_path, plan)

        loaded, loaded_sha256 = self.command._load_import_plan(
            self.plan_path,
            plan_sha256,
        )

        self.assertEqual(loaded, plan)
        self.assertEqual(loaded_sha256, plan_sha256)

    def test_rejects_plan_file_changed_after_review(self):
        plan = self._plan()
        plan_sha256 = self.command._write_import_plan(self.plan_path, plan)
        self.plan_path.write_text("{}\n", encoding="utf-8")

        with self.assertRaisesMessage(CommandError, "plan SHA-256 does not match"):
            self.command._load_import_plan(self.plan_path, plan_sha256)

    def test_rejects_contract_changed_without_integrity_update(self):
        plan = self._plan()
        plan["contract"]["target"]["database"] = "different"
        self.plan_path.write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        changed_sha256 = hashlib.sha256(self.plan_path.read_bytes()).hexdigest()

        with self.assertRaisesMessage(CommandError, "contract integrity check failed"):
            self.command._load_import_plan(self.plan_path, changed_sha256)

    def test_rejects_plan_from_previous_schema_version(self):
        plan = self._plan()
        plan["version"] = 1
        self.plan_path.write_text(
            json.dumps(plan, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        plan_sha256 = hashlib.sha256(self.plan_path.read_bytes()).hexdigest()

        with self.assertRaisesMessage(CommandError, "plan version is not supported"):
            self.command._load_import_plan(self.plan_path, plan_sha256)


class AtomicReplaceCommandTests(TestCase):
    def setUp(self):
        self.temp_dir = TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.input_path = Path(self.temp_dir.name) / "news.json"
        self.report_path = Path(self.temp_dir.name) / "report.md"
        self.plan_path = Path(self.temp_dir.name) / "import-plan.json"
        self.author = User.objects.create_user(username="cutover_author")
        self.matched_author = User.objects.create_user(username="drupal_author")
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
                        "drupal_author": {
                            "uid": 10,
                            "username": self.matched_author.username,
                        },
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
                        "drupal_author": {
                            "uid": 11,
                            "username": "missing_drupal_author",
                        },
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
        if "--apply" in mode:
            if not self.plan_path.exists():
                self._run_replace("--dry-run")
            return call_command(
                "import_drupal_news",
                "--apply",
                "--plan-file",
                str(self.plan_path),
                "--confirm-plan-sha256",
                hashlib.sha256(self.plan_path.read_bytes()).hexdigest(),
                "--report-file",
                str(self.report_path),
                stdout=StringIO(),
            )
        return call_command(
            "import_drupal_news",
            "--input",
            str(self.input_path),
            "--report-file",
            str(self.report_path),
            "--import-user",
            self.author.username,
            "--replace",
            "--strict",
            "--plan-file",
            str(self.plan_path),
            "--system-news-as-of",
            "2026-01-01T00:00:00Z",
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
        self.assertTrue(self.plan_path.is_file())
        self.assertIn("Import plan SHA-256", report)
        self.assertIn("## Author and Post-Date Attribution", report)
        self.assertIn("Exact Drupal username matches: `1`", report)
        self.assertIn("Explicit import-user fallbacks: `1`", report)
        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        self.assertEqual(plan["version"], 2)
        self.assertEqual(
            plan["expected"]["system_attribution"][0]["django_username"],
            self.matched_author.username,
        )
        self.assertEqual(
            plan["expected"]["integration_attribution"][0]["django_username"],
            self.author.username,
        )

    def test_replace_apply_replaces_both_feeds_and_builds_relationships(self):
        self._write_payload()

        self._run_replace("--apply")

        self.assertEqual(SystemStatusNews.objects.count(), 1)
        self.assertEqual(IntegrationNews.objects.count(), 1)
        system = SystemStatusNews.objects.get(outage_id=101)
        integration = IntegrationNews.objects.get(integration_news_id=201)
        posted_at = parse_datetime("2026-08-01T11:00:00Z")
        self.assertEqual(system.author, self.matched_author)
        self.assertEqual(integration.author, self.author)
        self.assertEqual(system.created_at, posted_at)
        self.assertEqual(system.published_at, posted_at)
        self.assertEqual(integration.created_at, posted_at)
        self.assertEqual(integration.published_at, posted_at)
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

    def test_case_different_drupal_username_uses_explicit_fallback(self):
        payload = self._payload()
        payload["SystemStatusNews"][0]["source_metadata"]["drupal_author"][
            "username"
        ] = self.matched_author.username.upper()
        self._write_payload(payload)

        self._run_replace("--dry-run")

        plan = json.loads(self.plan_path.read_text(encoding="utf-8"))
        attribution = plan["expected"]["system_attribution"][0]
        self.assertEqual(attribution["resolution"], "fallback")
        self.assertEqual(
            attribution["fallback_reason"], "no-django-username-match"
        )
        self.assertEqual(attribution["django_username"], self.author.username)

    def test_replace_apply_requires_matching_source_checksum(self):
        self._write_payload()
        self._run_replace("--dry-run")
        self.input_path.write_text(
            json.dumps({"SystemStatusNews": [], "IntegrationNews": []}),
            encoding="utf-8",
        )

        with self.assertRaisesMessage(CommandError, "source SHA-256 does not match"):
            self._run_replace("--apply")

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

        raw_plan_path = Path(self.temp_dir.name) / "raw-import-plan.json"
        call_command(
            "import_drupal_news",
            "--mysql-dump",
            str(raw_path),
            "--replace",
            "--system-news-as-of",
            "2026-01-01T00:00:00Z",
            "--dry-run",
            "--strict",
            "--confirm-database",
            self.database_name,
            "--confirm-host",
            self.database_host,
            "--suppress-notifications",
            "--plan-file",
            str(raw_plan_path),
            "--report-file",
            str(self.report_path),
            "--import-user",
            self.author.username,
            stdout=StringIO(),
        )
        call_command(
            "import_drupal_news",
            "--apply",
            "--plan-file",
            str(raw_plan_path),
            "--confirm-plan-sha256",
            hashlib.sha256(raw_plan_path.read_bytes()).hexdigest(),
            "--report-file",
            str(self.report_path),
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

    def test_apply_rolls_back_when_author_resolution_changes_after_dry_run(self):
        self._write_payload()
        self._run_replace("--dry-run")
        User.objects.create_user(username="missing_drupal_author")

        with self.assertRaisesMessage(CommandError, "staged import differs"):
            self._run_replace("--apply")

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(
            IntegrationNews.objects.filter(pk=self.old_integration.pk).exists()
        )
        self.assertFalse(SystemStatusNews.objects.filter(outage_id=101).exists())
        self.assertFalse(IntegrationNews.objects.filter(integration_news_id=201).exists())

    def test_replace_apply_rolls_back_when_target_changed_after_dry_run(self):
        self._write_payload()
        self._run_replace("--dry-run")
        extra = SystemStatusNews.objects.create(
            subject="Unexpected target drift",
            content="Created after plan review",
            infrastructure_news_type="degraded",
            outage_id=999,
            author=self.author,
        )

        with self.assertRaisesMessage(CommandError, "database outcome differs"):
            self._run_replace("--apply")

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(SystemStatusNews.objects.filter(pk=extra.pk).exists())
        self.assertTrue(IntegrationNews.objects.filter(pk=self.old_integration.pk).exists())
        self.assertFalse(SystemStatusNews.objects.filter(outage_id=101).exists())

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

        with self.assertRaisesMessage(
            CommandError,
            "configured write host does not match",
        ):
            call_command(
                "import_drupal_news",
                "--input",
                str(self.input_path),
                "--replace",
                "--system-news-as-of",
                "2026-01-01T00:00:00Z",
                "--dry-run",
                "--strict",
                "--plan-file",
                str(self.plan_path),
                "--confirm-database",
                self.database_name,
                "--confirm-host",
                "not-the-configured-host",
                stdout=StringIO(),
            )

        self.assertTrue(SystemStatusNews.objects.filter(pk=self.old_system.pk).exists())
        self.assertTrue(IntegrationNews.objects.filter(pk=self.old_integration.pk).exists())
