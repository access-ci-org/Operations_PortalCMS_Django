"""Import both Drupal news feeds from normalized JSON or a raw MySQL dump.

The raw-dump path is a guarded, atomic, one-time cutover workflow designed for
repeatable rehearsals before the final Drupal-to-Django replacement.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime
from integration_news.models import IntegrationElement, IntegrationNews
from resources.models import CiderInfrastructure

from infrastructure_news.drupal_mysql import (
    DrupalDumpError,
    parse_drupal_news_dump,
    sha256_file,
)
from infrastructure_news.models import SystemStatusNews

DEFAULT_INPUT = Path("database/drupal_backups/generated/drupal_news_normalized_for_django.json")
DEFAULT_REPORT = Path("database/drupal_backups/generated/drupal_news_import_dry_run.md")
IMPORT_PLAN_SCHEMA = "access-ci.drupal-news-import-plan"
IMPORT_PLAN_VERSION = 1
IMPORT_CONTRACT_VERSION = 1
MYSQL_BACKUP_NAME_RE = re.compile(
    r"^backup_database-(?P<timestamp>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:Z|[+-]\d{2}:\d{2}))\.mysql\.gz$"
)
KNOWN_SOURCE_CORRECTIONS = {
    "infrastructure-928-start-year": {
        "nid": 928,
        "source": "0026-01-07T12:50:36",
        "replacement": "2026-01-07T12:50:36",
    },
}


@dataclass
class ImportResult:
    total_records: int = 0
    system_records: int = 0
    integration_records: int = 0
    system_relationships: int = 0
    integration_relationships: int = 0
    integration_elements_created: int = 0
    integration_elements_updated: int = 0
    excluded_system_nids: List[int] = field(default_factory=list)
    system_news_as_of: Optional[str] = None
    cutoff_excluded_system_nids: List[int] = field(default_factory=list)
    source_corrections: List[str] = field(default_factory=list)
    plan_file: Optional[str] = None
    plan_sha256: Optional[str] = None
    created_system: int = 0
    updated_system: int = 0
    created_integration: int = 0
    updated_integration: int = 0
    deleted_system: int = 0
    deleted_integration: int = 0
    system_na_infrastructure: int = 0
    integration_na_element: int = 0
    unresolved_allowed_na: int = 0
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)

    def add_warning(self, message: str) -> None:
        self.warnings.append(message)

    def add_error(self, message: str) -> None:
        self.errors.append(message)


def _as_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    parsed = parse_datetime(value)
    if parsed is not None:
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    date_val = parse_date(value)
    if date_val is not None:
        return datetime.combine(date_val, datetime.min.time(), tzinfo=timezone.utc)
    return None


def _as_date(value: Optional[str]):
    if not value:
        return None
    parsed = parse_date(value)
    if parsed is not None:
        return parsed
    parsed_dt = parse_datetime(value)
    if parsed_dt is not None:
        return parsed_dt.date()
    return None


def _nid(record: Dict[str, Any]) -> str:
    meta = record.get("source_metadata", {}) or {}
    return str(meta.get("drupal_nid", "unknown"))


def _provenance_tag(record: Dict[str, Any]) -> str:
    nid = _nid(record)
    vid = (record.get("source_metadata", {}) or {}).get("drupal_vid")
    return f"[drupal_nid:{nid};drupal_vid:{vid}]"


def _source_author(record: Dict[str, Any]) -> str:
    source_author = (record.get("source_metadata", {}) or {}).get("drupal_author") or {}
    if isinstance(source_author, dict):
        return source_author.get("username") or source_author.get("mail") or "unknown"
    return "unknown"


class Command(BaseCommand):
    help = (
        "Import Drupal news into SystemStatusNews and IntegrationNews from normalized "
        "JSON or a raw MySQL dump, with guarded replacement and reporting."
    )

    def add_arguments(self, parser):
        source_group = parser.add_mutually_exclusive_group()
        source_group.add_argument(
            "--input",
            help=(
                "Path to normalized combined JSON. If neither source option is "
                f"provided, defaults to {DEFAULT_INPUT}."
            ),
        )
        source_group.add_argument(
            "--mysql-dump",
            help=(
                "Path to a raw Drupal mysqldump SQL file, optionally gzip-compressed. "
                "Direct source selection is for --dry-run; apply loads the exact "
                "source from the reviewed plan."
            ),
        )
        source_group.add_argument(
            "--mysql-dump-directory",
            help=(
                "For a replacement dry-run, select the newest readable regular file "
                "named backup_database-<timezone-aware ISO timestamp>.mysql.gz in "
                "this directory. Apply always uses the exact source bound in the plan."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Validate and simulate import without writing to PostgreSQL.",
        )
        parser.add_argument(
            "--report-file",
            default=str(DEFAULT_REPORT),
            help=f"Write markdown import report to this path (default: {DEFAULT_REPORT})",
        )
        parser.add_argument(
            "--import-user",
            default="drupaladmin",
            help="Fallback Django username to own imported records (default: drupaladmin).",
        )
        parser.add_argument(
            "--create-import-user",
            action="store_true",
            help="Create --import-user if missing (real import only).",
        )
        parser.add_argument(
            "--allow-na-affected-element",
            action="store_true",
            default=True,
            help="Allow unresolved affected elements to import as N/A (default: enabled).",
        )
        parser.add_argument(
            "--disallow-na-affected-element",
            action="store_false",
            dest="allow_na_affected_element",
            help="Fail on unresolved affected elements instead of importing as N/A.",
        )
        parser.add_argument(
            "--strict",
            action="store_true",
            help="Treat warnings as errors and abort import.",
        )
        parser.add_argument(
            "--replace",
            action="store_true",
            help=(
                "Replace both news feeds atomically. Requires --confirm-database and "
                "--confirm-host; writes also require --apply."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Apply a previously reviewed replacement plan. Requires --plan-file "
                "and --confirm-plan-sha256."
            ),
        )
        parser.add_argument(
            "--plan-file",
            help=(
                "With a replacement --dry-run, write the versioned JSON import plan "
                "to this new path. With --apply, load all bound import inputs from it."
            ),
        )
        parser.add_argument(
            "--confirm-plan-sha256",
            help=(
                "Required for --apply. Expected SHA-256 of the exact reviewed JSON "
                "plan file."
            ),
        )
        parser.add_argument(
            "--confirm-database",
            help="Expected configured PostgreSQL database name for --replace.",
        )
        parser.add_argument(
            "--confirm-host",
            help="Expected configured PostgreSQL write host for --replace.",
        )
        parser.add_argument(
            "--confirm-source-sha256",
            help=(
                "Optional expected SHA-256 for a dry-run source. Apply loads and "
                "revalidates the source SHA-256 bound in the reviewed plan."
            ),
        )
        parser.add_argument(
            "--suppress-notifications",
            action="store_true",
            help="Force imported infrastructure-news email and Slack flags off.",
        )
        parser.add_argument(
            "--exclude-system-nid",
            action="append",
            type=int,
            default=[],
            help=(
                "Explicitly exclude one Infrastructure News Drupal nid. Repeat for "
                "multiple IDs. The requested ID must exist in the source."
            ),
        )
        parser.add_argument(
            "--system-news-as-of",
            help=(
                "Required for replacement imports. Retain only current or future "
                "Infrastructure News as of this timezone-aware ISO-8601 timestamp. "
                "Apply loads the exact value from the reviewed plan."
            ),
        )
        parser.add_argument(
            "--source-correction",
            action="append",
            choices=sorted(KNOWN_SOURCE_CORRECTIONS),
            default=[],
            help=(
                "Apply a named, exact-match source correction. Repeat if needed. "
                "The import fails if the expected original value is not present."
            ),
        )

    def handle(self, *args, **options):
        report_path = Path(options["report_file"])
        plan_path = Path(options["plan_file"]) if options.get("plan_file") else None
        plan_data: Optional[Dict[str, Any]] = None
        plan_file_sha256: Optional[str] = None
        dry_run = bool(options["dry_run"])
        apply = bool(options["apply"])
        if apply:
            if plan_path is None or not options.get("confirm_plan_sha256"):
                raise CommandError(
                    "--apply requires --plan-file and --confirm-plan-sha256."
                )
            conflicting_options = [
                name
                for name in (
                    "input",
                    "mysql_dump",
                    "mysql_dump_directory",
                    "replace",
                    "dry_run",
                    "strict",
                    "confirm_database",
                    "confirm_host",
                    "confirm_source_sha256",
                    "confirm_system_count",
                    "confirm_integration_count",
                    "suppress_notifications",
                    "system_news_as_of",
                    "create_import_user",
                )
                if options.get(name)
            ]
            if options.get("exclude_system_nid"):
                conflicting_options.append("exclude_system_nid")
            if options.get("source_correction"):
                conflicting_options.append("source_correction")
            if options.get("allow_na_affected_element") is False:
                conflicting_options.append("disallow_na_affected_element")
            if options.get("import_user") != "drupaladmin":
                conflicting_options.append("import_user")
            if conflicting_options:
                raise CommandError(
                    "--apply loads bound import options from --plan-file; remove: "
                    + ", ".join(
                        f"--{name.replace('_', '-')}"
                        for name in conflicting_options
                    )
                )
            plan_data, plan_file_sha256 = self._load_import_plan(
                plan_path=plan_path,
                confirmed_sha256=str(options["confirm_plan_sha256"]),
            )
            contract = plan_data["contract"]
            source_contract = contract["source"]
            option_contract = contract["options"]
            adjustment_contract = contract["adjustments"]
            target_contract = contract["target"]
            if contract["python_executable"] != sys.executable:
                raise CommandError(
                    "Refusing apply: import plan was produced by a different Python "
                    "executable/release."
                )

            source_kind = source_contract["kind"]
            input_path = Path(source_contract["path"])
            mysql_dump = str(input_path) if source_kind == "mysql-dump" else None
            dry_run = False
            replace = bool(option_contract["replace"])
            strict = bool(option_contract["strict"])
            excluded_system_nids = list(
                adjustment_contract["excluded_system_nids"]
            )
            source_correction_names = [
                correction["name"]
                for correction in adjustment_contract["source_corrections"]
            ]
            system_news_as_of_raw = adjustment_contract["system_news_as_of"]
            options["confirm_database"] = target_contract["database"]
            options["confirm_host"] = target_contract["host"]
            options["confirm_source_sha256"] = source_contract["sha256"]
            options["confirm_system_count"] = plan_data["expected"]["system_records"]
            options["confirm_integration_count"] = plan_data["expected"][
                "integration_records"
            ]
            options["suppress_notifications"] = bool(
                option_contract["suppress_notifications"]
            )
            options["allow_na_affected_element"] = bool(
                option_contract["allow_na_affected_element"]
            )
            options["create_import_user"] = bool(
                option_contract["create_import_user"]
            )
            options["import_user"] = option_contract["import_user"]
        else:
            mysql_dump = options.get("mysql_dump")
            mysql_dump_directory = options.get("mysql_dump_directory")
            if mysql_dump_directory:
                if not dry_run:
                    raise CommandError(
                        "--mysql-dump-directory is only valid with --dry-run; "
                        "apply uses the exact source bound in --plan-file."
                    )
                input_path = self._select_newest_mysql_dump(
                    Path(mysql_dump_directory)
                )
                mysql_dump = str(input_path)
            else:
                input_path = Path(mysql_dump or options.get("input") or DEFAULT_INPUT)
            source_kind = "mysql-dump" if mysql_dump else "normalized-json"
            strict = bool(options["strict"])
            replace = bool(options["replace"])
            excluded_system_nids = options.get("exclude_system_nid") or []
            source_correction_names = options.get("source_correction") or []
            system_news_as_of_raw = options.get("system_news_as_of")

        if source_kind not in {"mysql-dump", "normalized-json"}:
            raise CommandError(f"Unsupported import-plan source kind: {source_kind!r}.")

        if replace and not system_news_as_of_raw:
            raise CommandError(
                "--replace requires --system-news-as-of so past Infrastructure News "
                "is excluded deterministically."
            )
        system_news_as_of = (
            self._parse_system_news_as_of(system_news_as_of_raw)
            if system_news_as_of_raw
            else None
        )

        if len(excluded_system_nids) != len(set(excluded_system_nids)):
            raise CommandError("Duplicate --exclude-system-nid values are not permitted.")
        if any(value <= 0 for value in excluded_system_nids):
            raise CommandError("--exclude-system-nid values must be positive integers.")
        if len(source_correction_names) != len(set(source_correction_names)):
            raise CommandError("Duplicate --source-correction values are not permitted.")

        start_datetime_corrections = {
            int(KNOWN_SOURCE_CORRECTIONS[name]["nid"]): (
                str(KNOWN_SOURCE_CORRECTIONS[name]["source"]),
                str(KNOWN_SOURCE_CORRECTIONS[name]["replacement"]),
            )
            for name in source_correction_names
        }
        if plan_data is not None:
            expected_corrections = plan_data["contract"]["adjustments"][
                "source_corrections"
            ]
            actual_corrections = [
                {"name": name, **KNOWN_SOURCE_CORRECTIONS[name]}
                for name in source_correction_names
            ]
            if expected_corrections != actual_corrections:
                raise CommandError(
                    "Refusing apply: named source-correction definitions changed "
                    "since the dry-run plan was produced."
                )
        overlapping_adjustments = sorted(
            set(excluded_system_nids) & set(start_datetime_corrections)
        )
        if overlapping_adjustments:
            raise CommandError(
                "A SystemStatusNews nid cannot be both excluded and corrected: "
                + ", ".join(str(value) for value in overlapping_adjustments)
            )

        if apply and not replace:
            raise CommandError("--apply is only valid with --replace.")
        if options.get("confirm_plan_sha256") and not apply:
            raise CommandError("--confirm-plan-sha256 is only valid with --apply.")
        if replace and dry_run:
            if plan_path is None:
                raise CommandError(
                    "A replacement --dry-run requires --plan-file."
                )
            if not strict:
                raise CommandError(
                    "A replacement --dry-run that writes a plan requires --strict."
                )
            if plan_path.exists():
                raise CommandError(
                    f"Refusing to overwrite existing import plan: {plan_path}"
                )
            resolved_plan = plan_path.resolve()
            if resolved_plan in {input_path.resolve(), report_path.resolve()}:
                raise CommandError(
                    "--plan-file must differ from the source and Markdown report paths."
                )
        elif plan_path is not None and not apply:
            raise CommandError(
                "--plan-file is only valid with a replacement --dry-run or --apply."
            )
        if mysql_dump and not replace:
            raise CommandError(
                "--mysql-dump requires --replace; raw cutover data must replace both "
                "news feeds atomically."
            )
        if mysql_dump and options.get("create_import_user"):
            raise CommandError(
                "Raw-dump cutover imports require an existing --import-user; "
                "--create-import-user is not permitted."
            )
        if mysql_dump and not options.get("suppress_notifications"):
            raise CommandError(
                "Raw-dump imports require --suppress-notifications."
            )
        if replace:
            self._validate_replace_target(
                confirm_database=options.get("confirm_database"),
                confirm_host=options.get("confirm_host"),
            )
            if plan_data is not None:
                configured_port = str(
                    settings.DATABASES["default"].get("PORT") or ""
                )
                planned_port = str(
                    plan_data["contract"]["target"].get("port") or ""
                )
                if configured_port != planned_port:
                    raise CommandError(
                        "Refusing apply: configured database port differs from "
                        "the reviewed import plan."
                    )
            if dry_run and apply:
                raise CommandError("Choose either --dry-run or --apply, not both.")
            if not dry_run and not apply:
                raise CommandError(
                    "A replacement write requires --apply. Use --dry-run to review the plan first."
                )

        if apply and not options.get("confirm_source_sha256"):
            raise CommandError("Reviewed import plan does not bind a source SHA-256.")
        if mysql_dump and apply and not strict:
            raise CommandError("A raw-dump --apply requires --strict.")

        if not input_path.exists():
            raise CommandError(f"Input file does not exist: {input_path}")

        source_sha256 = sha256_file(input_path)
        confirmed_sha256 = options.get("confirm_source_sha256")
        if confirmed_sha256 and confirmed_sha256.lower() != source_sha256:
            confirmation_source = (
                "the reviewed import plan"
                if plan_data is not None
                else "--confirm-source-sha256"
            )
            raise CommandError(
                f"Refusing import: source SHA-256 does not match {confirmation_source}."
            )

        source_warnings: List[str] = []
        excluded_system_nids_found: List[int] = []
        source_corrections_applied: List[str] = []
        result = ImportResult(
            system_news_as_of=system_news_as_of_raw,
            plan_file=str(plan_path) if plan_path else None,
            plan_sha256=plan_file_sha256,
        )
        if mysql_dump:
            try:
                parsed_dump = parse_drupal_news_dump(
                    input_path,
                    infrastructure_type_choices=SystemStatusNews.INFRASTRUCTURE_NEWS_TYPES,
                    integration_type_choices=IntegrationNews.INTEGRATION_NEWS_TYPES,
                    integration_element_choices=IntegrationNews.AFFECTED_ELEMENTS,
                    excluded_system_nids=excluded_system_nids,
                    system_start_datetime_corrections=start_datetime_corrections,
                )
            except DrupalDumpError as exc:
                result.add_error(str(exc))
                self._write_report(
                    report_path=report_path,
                    result=result,
                    dry_run=dry_run,
                    input_path=input_path,
                    source_kind=source_kind,
                    source_sha256=source_sha256,
                )
                raise CommandError(str(exc)) from exc
            if parsed_dump.sha256 != source_sha256:
                raise CommandError("Source changed while it was being parsed; rerun the dry-run.")
            payload = parsed_dump.payload
            source_warnings.extend(parsed_dump.warnings)
            excluded_system_nids_found.extend(parsed_dump.excluded_system_nids)
            source_corrections_applied.extend(parsed_dump.source_corrections)
        else:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
        system_records = payload.get("SystemStatusNews", [])
        integration_records = payload.get("IntegrationNews", [])
        if replace and (not isinstance(system_records, list) or not system_records):
            raise CommandError(
                "Replacement requires a nonempty SystemStatusNews source list "
                "before cutoff filtering."
            )
        if not mysql_dump and (excluded_system_nids or start_datetime_corrections):
            (
                system_records,
                excluded_system_nids_found,
                source_corrections_applied,
            ) = self._adjust_normalized_system_records(
                records=system_records,
                excluded_system_nids=set(excluded_system_nids),
                start_datetime_corrections=start_datetime_corrections,
            )
        cutoff_excluded_system_nids: List[int] = []
        if system_news_as_of is not None:
            system_records, cutoff_excluded_system_nids = (
                self._filter_system_records_as_of(
                    records=system_records,
                    cutoff=system_news_as_of,
                )
            )

        if apply:
            expected_system_count = options.get("confirm_system_count")
            expected_integration_count = options.get("confirm_integration_count")
            if expected_system_count is None or expected_integration_count is None:
                raise CommandError(
                    "Reviewed import plan does not bind both retained feed counts."
                )
            if expected_system_count != len(system_records):
                raise CommandError(
                    "Refusing import: SystemStatusNews source count differs from "
                    f"the reviewed plan ({len(system_records)} != "
                    f"{expected_system_count})."
                )
            if expected_integration_count != len(integration_records):
                raise CommandError(
                    "Refusing import: IntegrationNews source count differs from "
                    f"the reviewed plan ({len(integration_records)} != "
                    f"{expected_integration_count})."
                )

        expected_system_ids: set[int] = set()
        expected_integration_ids: set[int] = set()
        if replace:
            expected_system_ids = self._validated_source_ids(
                records=system_records,
                feed_name="SystemStatusNews",
                allow_empty=True,
            )
            expected_integration_ids = self._validated_source_ids(
                records=integration_records,
                feed_name="IntegrationNews",
            )

        self.stdout.write(f"Input: {input_path}")
        self.stdout.write(f"Input SHA-256: {source_sha256}")
        self.stdout.write(
            f"Records detected -> SystemStatusNews: {len(system_records)}, IntegrationNews: {len(integration_records)}"
        )

        result.total_records = len(system_records) + len(integration_records)
        result.system_records = len(system_records)
        result.integration_records = len(integration_records)
        result.excluded_system_nids = excluded_system_nids_found
        result.cutoff_excluded_system_nids = cutoff_excluded_system_nids
        result.source_corrections = source_corrections_applied
        result.system_relationships = sum(
            len(
                (record.get("source_metadata", {}) or {}).get(
                    "affected_infrastructure_nodes"
                )
                or []
            )
            for record in system_records
        )
        result.integration_relationships = sum(
            len(record.get("affected_elements") or [])
            if record.get("affected_elements") is not None
            else int(bool(record.get("affected_element")))
            for record in integration_records
        )
        result.warnings.extend(source_warnings)
        if plan_data is not None:
            self._validate_plan_staging(
                plan_data=plan_data,
                result=result,
                expected_system_ids=expected_system_ids,
                expected_integration_ids=expected_integration_ids,
            )

        try:
            with transaction.atomic():
                import_user = self._resolve_import_user(
                    username=options["import_user"],
                    create_missing=bool(options["create_import_user"]),
                    dry_run=dry_run,
                    result=result,
                )
                integration_elements = self._ensure_integration_elements(
                    dry_run=dry_run,
                    result=result,
                )

                if replace:
                    result.deleted_system = SystemStatusNews.objects.count()
                    result.deleted_integration = IntegrationNews.objects.count()
                    if not dry_run:
                        SystemStatusNews.objects.all().delete()
                        IntegrationNews.objects.all().delete()

                for record in system_records:
                    self._import_system_record(
                        record=record,
                        import_user=import_user,
                        dry_run=dry_run,
                        result=result,
                        force_create=replace,
                        suppress_notifications=bool(options["suppress_notifications"]),
                    )
                for record in integration_records:
                    self._import_integration_record(
                        record=record,
                        import_user=import_user,
                        integration_elements=integration_elements,
                        allow_na_affected_element=bool(options["allow_na_affected_element"]),
                        dry_run=dry_run,
                        result=result,
                        force_create=replace,
                    )

                if replace and not dry_run:
                    self._validate_replacement(
                        expected_system_ids=expected_system_ids,
                        expected_integration_ids=expected_integration_ids,
                        system_records=system_records,
                        integration_records=integration_records,
                        suppress_notifications=bool(options["suppress_notifications"]),
                    )

                if strict and result.warnings:
                    raise CommandError(
                        f"Strict mode enabled and warnings found ({len(result.warnings)}). "
                        "See report for details."
                    )

                if plan_data is not None:
                    self._validate_plan_outcome(plan_data=plan_data, result=result)

                if dry_run:
                    # Ensure absolutely no writes in dry-run mode.
                    transaction.set_rollback(True)

        except Exception as exc:
            result.add_error(str(exc))
            self._write_report(
                report_path=report_path,
                result=result,
                dry_run=dry_run,
                input_path=input_path,
                source_kind=source_kind,
                source_sha256=source_sha256,
            )
            raise

        if replace and dry_run:
            import_plan = self._build_import_plan(
                input_path=input_path,
                source_kind=source_kind,
                source_sha256=source_sha256,
                result=result,
                expected_system_ids=expected_system_ids,
                expected_integration_ids=expected_integration_ids,
                excluded_system_nids=excluded_system_nids,
                source_correction_names=source_correction_names,
                options=options,
            )
            result.plan_sha256 = self._write_import_plan(
                plan_path=plan_path,
                plan_data=import_plan,
            )

        self._write_report(
            report_path=report_path,
            result=result,
            dry_run=dry_run,
            input_path=input_path,
            source_kind=source_kind,
            source_sha256=source_sha256,
        )
        self._emit_summary(result=result, dry_run=dry_run, report_path=report_path)

    def _select_newest_mysql_dump(self, directory: Path) -> Path:
        try:
            resolved_directory = directory.resolve(strict=True)
        except OSError as exc:
            raise CommandError(
                f"MySQL dump directory cannot be resolved: {directory}"
            ) from exc
        if not resolved_directory.is_dir():
            raise CommandError(
                f"MySQL dump directory is not a directory: {resolved_directory}"
            )
        if not os.access(resolved_directory, os.R_OK | os.X_OK):
            raise CommandError(
                f"MySQL dump directory is not readable: {resolved_directory}"
            )

        candidates: List[tuple[datetime, Path]] = []
        for candidate in sorted(resolved_directory.glob("backup_database-*.mysql.gz")):
            match = MYSQL_BACKUP_NAME_RE.fullmatch(candidate.name)
            if match is None:
                raise CommandError(
                    f"Malformed MySQL backup filename in {resolved_directory}: "
                    f"{candidate.name}"
                )
            if candidate.is_symlink() or not candidate.is_file():
                raise CommandError(
                    f"MySQL backup candidate is not a regular file: {candidate}"
                )
            if not os.access(candidate, os.R_OK):
                raise CommandError(
                    f"MySQL backup candidate is not readable: {candidate}"
                )
            parsed = parse_datetime(match.group("timestamp"))
            if parsed is None or parsed.tzinfo is None:
                raise CommandError(
                    f"MySQL backup filename has an invalid timezone-aware timestamp: "
                    f"{candidate.name}"
                )
            candidates.append(
                (parsed.astimezone(timezone.utc), candidate.resolve(strict=True))
            )

        if not candidates:
            raise CommandError(
                "No readable MySQL backups match "
                "backup_database-<timezone-aware ISO timestamp>.mysql.gz in "
                f"{resolved_directory}."
            )
        newest_timestamp = max(timestamp for timestamp, _ in candidates)
        newest_paths = [
            path for timestamp, path in candidates if timestamp == newest_timestamp
        ]
        if len(newest_paths) != 1:
            raise CommandError(
                "Multiple MySQL backups represent the same newest instant: "
                + ", ".join(str(path) for path in newest_paths)
            )
        return newest_paths[0]

    def _build_import_plan(
        self,
        input_path: Path,
        source_kind: str,
        source_sha256: str,
        result: ImportResult,
        expected_system_ids: set[int],
        expected_integration_ids: set[int],
        excluded_system_nids: List[int],
        source_correction_names: List[str],
        options: Dict[str, Any],
    ) -> Dict[str, Any]:
        configured = settings.DATABASES["default"]
        plan: Dict[str, Any] = {
            "schema": IMPORT_PLAN_SCHEMA,
            "version": IMPORT_PLAN_VERSION,
            "created_at_utc": datetime.now(timezone.utc).isoformat(),
            "contract": {
                "contract_version": IMPORT_CONTRACT_VERSION,
                "python_executable": sys.executable,
                "source": {
                    "kind": source_kind,
                    "path": str(input_path.resolve()),
                    "sha256": source_sha256,
                },
                "target": {
                    "database": str(configured.get("NAME") or ""),
                    "host": str(configured.get("HOST") or ""),
                    "port": str(configured.get("PORT") or ""),
                },
                "options": {
                    "replace": True,
                    "strict": True,
                    "suppress_notifications": bool(
                        options["suppress_notifications"]
                    ),
                    "allow_na_affected_element": bool(
                        options["allow_na_affected_element"]
                    ),
                    "create_import_user": bool(options["create_import_user"]),
                    "import_user": str(options["import_user"]),
                },
                "adjustments": {
                    "system_news_as_of": result.system_news_as_of,
                    "excluded_system_nids": sorted(excluded_system_nids),
                    "source_corrections": [
                        {"name": name, **KNOWN_SOURCE_CORRECTIONS[name]}
                        for name in sorted(source_correction_names)
                    ],
                },
            },
            "expected": {
                "system_records": result.system_records,
                "integration_records": result.integration_records,
                "system_relationships": result.system_relationships,
                "integration_relationships": result.integration_relationships,
                "system_ids": sorted(expected_system_ids),
                "integration_ids": sorted(expected_integration_ids),
                "excluded_system_nids": result.excluded_system_nids,
                "cutoff_excluded_system_nids": result.cutoff_excluded_system_nids,
                "source_corrections_applied": result.source_corrections,
                "outcome": self._result_outcome_contract(result),
            },
        }
        plan["contract_sha256"] = self._import_plan_contract_sha256(plan)
        return plan

    def _write_import_plan(
        self,
        plan_path: Optional[Path],
        plan_data: Dict[str, Any],
    ) -> str:
        if plan_path is None:
            raise CommandError("Internal error: replacement dry-run has no plan path.")
        plan_path.parent.mkdir(parents=True, exist_ok=True)
        serialized = json.dumps(plan_data, indent=2, sort_keys=True) + "\n"
        try:
            with plan_path.open("x", encoding="utf-8") as plan_handle:
                plan_handle.write(serialized)
        except FileExistsError as exc:
            raise CommandError(
                f"Refusing to overwrite existing import plan: {plan_path}"
            ) from exc
        except OSError as exc:
            raise CommandError(
                f"Unable to write import plan {plan_path}: {exc}"
            ) from exc
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def _load_import_plan(
        self,
        plan_path: Path,
        confirmed_sha256: str,
    ) -> tuple[Dict[str, Any], str]:
        if not plan_path.is_file():
            raise CommandError(f"Import plan does not exist: {plan_path}")
        actual_sha256 = sha256_file(plan_path)
        if actual_sha256 != confirmed_sha256.lower():
            raise CommandError(
                "Refusing apply: import plan SHA-256 does not match "
                "--confirm-plan-sha256."
            )
        try:
            plan_data = json.loads(plan_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as exc:
            raise CommandError(
                f"Unable to read JSON import plan {plan_path}: {exc}"
            ) from exc
        self._validate_import_plan_schema(plan_data)
        return plan_data, actual_sha256

    def _validate_import_plan_schema(self, plan_data: Any) -> None:
        top_level_keys = {
            "schema",
            "version",
            "created_at_utc",
            "contract",
            "expected",
            "contract_sha256",
        }
        contract_keys = {
            "contract_version",
            "python_executable",
            "source",
            "target",
            "options",
            "adjustments",
        }
        expected_keys = {
            "system_records",
            "integration_records",
            "system_relationships",
            "integration_relationships",
            "system_ids",
            "integration_ids",
            "excluded_system_nids",
            "cutoff_excluded_system_nids",
            "source_corrections_applied",
            "outcome",
        }
        outcome_keys = set(self._result_outcome_contract(ImportResult()))
        try:
            valid_shape = (
                isinstance(plan_data, dict)
                and set(plan_data) == top_level_keys
                and set(plan_data["contract"]) == contract_keys
                and set(plan_data["contract"]["source"])
                == {"kind", "path", "sha256"}
                and set(plan_data["contract"]["target"])
                == {"database", "host", "port"}
                and set(plan_data["contract"]["options"])
                == {
                    "replace",
                    "strict",
                    "suppress_notifications",
                    "allow_na_affected_element",
                    "create_import_user",
                    "import_user",
                }
                and set(plan_data["contract"]["adjustments"])
                == {
                    "system_news_as_of",
                    "excluded_system_nids",
                    "source_corrections",
                }
                and set(plan_data["expected"]) == expected_keys
                and set(plan_data["expected"]["outcome"]) == outcome_keys
            )
        except (KeyError, TypeError):
            valid_shape = False
        if not valid_shape:
            raise CommandError("Import plan has an invalid or unsupported JSON shape.")
        if plan_data["schema"] != IMPORT_PLAN_SCHEMA:
            raise CommandError("Import plan schema is not supported.")
        if plan_data["version"] != IMPORT_PLAN_VERSION:
            raise CommandError("Import plan version is not supported.")
        created_at = parse_datetime(plan_data["created_at_utc"])
        if created_at is None or created_at.tzinfo is None:
            raise CommandError("Import plan creation timestamp is invalid.")
        contract = plan_data["contract"]
        if contract["contract_version"] != IMPORT_CONTRACT_VERSION:
            raise CommandError("Import plan contract version is not supported.")
        if self._import_plan_contract_sha256(plan_data) != plan_data["contract_sha256"]:
            raise CommandError("Import plan contract integrity check failed.")
        if (
            not isinstance(contract["python_executable"], str)
            or not Path(contract["python_executable"]).is_absolute()
        ):
            raise CommandError("Import plan Python executable is invalid.")

        source = contract["source"]
        if source["kind"] not in {"mysql-dump", "normalized-json"}:
            raise CommandError("Import plan contains an unsupported source kind.")
        if not isinstance(source["path"], str) or not Path(
            source["path"]
        ).is_absolute():
            raise CommandError("Import plan source path must be absolute.")
        if not self._is_sha256(source["sha256"]):
            raise CommandError("Import plan source SHA-256 is invalid.")
        if not self._is_sha256(plan_data["contract_sha256"]):
            raise CommandError("Import plan contract SHA-256 is invalid.")
        target = contract["target"]
        if any(not isinstance(target[name], str) for name in ("database", "host", "port")):
            raise CommandError("Import plan target values are invalid.")
        if not target["database"] or not target["host"]:
            raise CommandError("Import plan target database and host are required.")

        options = contract["options"]
        boolean_options = (
            "replace",
            "strict",
            "suppress_notifications",
            "allow_na_affected_element",
            "create_import_user",
        )
        if any(not isinstance(options[name], bool) for name in boolean_options):
            raise CommandError("Import plan contains a non-boolean execution option.")
        if not options["replace"] or not options["strict"]:
            raise CommandError("Import plan must bind strict atomic replacement.")
        if source["kind"] == "mysql-dump" and (
            not options["suppress_notifications"] or options["create_import_user"]
        ):
            raise CommandError(
                "Raw-dump import plan violates notification or import-user safeguards."
            )
        if not isinstance(options["import_user"], str) or not options["import_user"]:
            raise CommandError("Import plan import user is invalid.")

        adjustments = contract["adjustments"]
        self._parse_system_news_as_of(adjustments["system_news_as_of"])
        self._validate_plan_id_list(
            adjustments["excluded_system_nids"],
            "explicit SystemStatusNews exclusions",
            allow_empty=True,
        )
        corrections = adjustments["source_corrections"]
        if not isinstance(corrections, list) or any(
            not isinstance(correction, dict)
            or set(correction) != {"name", "nid", "source", "replacement"}
            for correction in corrections
        ):
            raise CommandError("Import plan source corrections are malformed.")
        if any(
            correction["name"] not in KNOWN_SOURCE_CORRECTIONS
            or correction
            != {
                "name": correction["name"],
                **KNOWN_SOURCE_CORRECTIONS.get(correction["name"], {}),
            }
            for correction in corrections
        ):
            raise CommandError(
                "Import plan source-correction definition is not currently supported."
            )
        correction_names = [correction["name"] for correction in corrections]
        if correction_names != sorted(set(correction_names)):
            raise CommandError(
                "Import plan source corrections must be sorted and unique."
            )

        expected = plan_data["expected"]
        count_fields = (
            "system_records",
            "integration_records",
            "system_relationships",
            "integration_relationships",
        )
        if any(
            isinstance(expected[name], bool)
            or not isinstance(expected[name], int)
            or expected[name] < 0
            for name in count_fields
        ):
            raise CommandError("Import plan contains an invalid expected count.")
        self._validate_plan_id_list(
            expected["system_ids"], "SystemStatusNews IDs", allow_empty=True
        )
        self._validate_plan_id_list(
            expected["integration_ids"], "IntegrationNews IDs", allow_empty=False
        )
        self._validate_plan_id_list(
            expected["excluded_system_nids"],
            "applied SystemStatusNews exclusions",
            allow_empty=True,
        )
        self._validate_plan_id_list(
            expected["cutoff_excluded_system_nids"],
            "cutoff-excluded SystemStatusNews IDs",
            allow_empty=True,
        )
        if not isinstance(expected["source_corrections_applied"], list) or any(
            not isinstance(value, str)
            for value in expected["source_corrections_applied"]
        ):
            raise CommandError("Import plan applied corrections are malformed.")
        if any(
            isinstance(value, bool) or not isinstance(value, int) or value < 0
            for value in expected["outcome"].values()
        ):
            raise CommandError("Import plan expected outcome is malformed.")
        if expected["system_records"] != len(expected["system_ids"]):
            raise CommandError("Import plan SystemStatusNews count and IDs differ.")
        if expected["integration_records"] != len(expected["integration_ids"]):
            raise CommandError("Import plan IntegrationNews count and IDs differ.")
        if (
            expected["excluded_system_nids"]
            != adjustments["excluded_system_nids"]
        ):
            raise CommandError("Import plan explicit exclusion sets differ.")
        if set(expected["excluded_system_nids"]) & set(
            expected["cutoff_excluded_system_nids"]
        ):
            raise CommandError("Import plan exclusion sets overlap.")
        if len(expected["source_corrections_applied"]) != len(corrections):
            raise CommandError("Import plan source correction counts differ.")
        outcome = expected["outcome"]
        if (
            outcome["created_system"] != expected["system_records"]
            or outcome["created_integration"] != expected["integration_records"]
            or outcome["updated_system"] != 0
            or outcome["updated_integration"] != 0
        ):
            raise CommandError("Import plan replacement outcome is inconsistent.")

    def _validate_plan_id_list(
        self,
        values: Any,
        label: str,
        allow_empty: bool,
    ) -> None:
        if (
            not isinstance(values, list)
            or (not values and not allow_empty)
            or any(
                isinstance(value, bool)
                or not isinstance(value, int)
                or value <= 0
                for value in values
            )
            or values != sorted(set(values))
        ):
            raise CommandError(
                f"Import plan {label} must be sorted unique positive integers."
            )

    def _import_plan_contract_sha256(self, plan_data: Dict[str, Any]) -> str:
        digest_payload = {
            key: value
            for key, value in plan_data.items()
            if key != "contract_sha256"
        }
        canonical = json.dumps(
            digest_payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def _is_sha256(self, value: Any) -> bool:
        if not isinstance(value, str) or len(value) != 64:
            return False
        try:
            int(value, 16)
        except ValueError:
            return False
        return True

    def _validate_plan_staging(
        self,
        plan_data: Dict[str, Any],
        result: ImportResult,
        expected_system_ids: set[int],
        expected_integration_ids: set[int],
    ) -> None:
        expected = plan_data["expected"]
        actual = {
            "system_records": result.system_records,
            "integration_records": result.integration_records,
            "system_relationships": result.system_relationships,
            "integration_relationships": result.integration_relationships,
            "system_ids": sorted(expected_system_ids),
            "integration_ids": sorted(expected_integration_ids),
            "excluded_system_nids": result.excluded_system_nids,
            "cutoff_excluded_system_nids": result.cutoff_excluded_system_nids,
            "source_corrections_applied": result.source_corrections,
        }
        mismatches = [name for name, value in actual.items() if expected[name] != value]
        if mismatches:
            raise CommandError(
                "Refusing apply: staged import differs from the reviewed plan: "
                + ", ".join(mismatches)
            )

    def _validate_plan_outcome(
        self,
        plan_data: Dict[str, Any],
        result: ImportResult,
    ) -> None:
        actual = self._result_outcome_contract(result)
        expected = plan_data["expected"]["outcome"]
        mismatches = [name for name, value in actual.items() if expected[name] != value]
        if mismatches:
            raise CommandError(
                "Refusing apply: database outcome differs from the reviewed plan: "
                + ", ".join(mismatches)
            )

    def _result_outcome_contract(self, result: ImportResult) -> Dict[str, int]:
        return {
            "integration_elements_created": result.integration_elements_created,
            "integration_elements_updated": result.integration_elements_updated,
            "created_system": result.created_system,
            "updated_system": result.updated_system,
            "created_integration": result.created_integration,
            "updated_integration": result.updated_integration,
            "deleted_system": result.deleted_system,
            "deleted_integration": result.deleted_integration,
            "system_na_infrastructure": result.system_na_infrastructure,
            "integration_na_element": result.integration_na_element,
            "unresolved_allowed_na": result.unresolved_allowed_na,
        }

    def _adjust_normalized_system_records(
        self,
        records: Any,
        excluded_system_nids: set[int],
        start_datetime_corrections: Dict[int, tuple[str, str]],
    ) -> tuple[List[Dict[str, Any]], List[int], List[str]]:
        if not isinstance(records, list):
            raise CommandError("SystemStatusNews must be a JSON list.")

        nid_counts: Dict[int, int] = {}
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise CommandError(
                    f"SystemStatusNews record {index} must be a JSON object."
                )
            raw_nid = (record.get("source_metadata", {}) or {}).get("drupal_nid")
            try:
                nid = int(raw_nid)
            except (TypeError, ValueError):
                continue
            nid_counts[nid] = nid_counts.get(nid, 0) + 1

        requested_nids = excluded_system_nids | set(start_datetime_corrections)
        for nid in sorted(requested_nids):
            if nid_counts.get(nid, 0) != 1:
                raise CommandError(
                    f"Requested SystemStatusNews adjustment nid={nid} must match "
                    f"exactly one input record; found {nid_counts.get(nid, 0)}."
                )

        adjusted_records = []
        exclusions_found: List[int] = []
        corrections_applied: List[str] = []
        corrected_nids: set[int] = set()
        for record in records:
            raw_nid = (record.get("source_metadata", {}) or {}).get("drupal_nid")
            try:
                nid = int(raw_nid)
            except (TypeError, ValueError):
                adjusted_records.append(record)
                continue
            if nid in excluded_system_nids:
                exclusions_found.append(nid)
                continue

            correction = start_datetime_corrections.get(nid)
            if correction is not None:
                expected_source, replacement = correction
                actual_source = record.get("start_datetime")
                if actual_source != expected_source:
                    raise CommandError(
                        f"SystemStatusNews nid={nid} start date correction expected "
                        f"{expected_source!r}, found {actual_source!r}; refusing to "
                        "alter an unexpected source value."
                    )
                record = dict(record)
                record["start_datetime"] = replacement
                corrections_applied.append(
                    f"SystemStatusNews nid={nid} start_datetime: "
                    f"{expected_source!r} -> {replacement!r}"
                )
                corrected_nids.add(nid)
            adjusted_records.append(record)

        missing_exclusions = sorted(excluded_system_nids - set(exclusions_found))
        if missing_exclusions:
            raise CommandError(
                "Requested SystemStatusNews exclusions were not present in the input: "
                + ", ".join(str(value) for value in missing_exclusions)
            )
        missing_corrections = sorted(
            set(start_datetime_corrections) - corrected_nids
        )
        if missing_corrections:
            raise CommandError(
                "Requested SystemStatusNews corrections were not applied: "
                + ", ".join(str(value) for value in missing_corrections)
            )
        return adjusted_records, sorted(exclusions_found), corrections_applied

    def _parse_system_news_as_of(self, value: str) -> datetime:
        parsed = parse_datetime(value)
        if parsed is None or parsed.tzinfo is None:
            raise CommandError(
                "--system-news-as-of must be a timezone-aware ISO-8601 timestamp "
                "such as 2026-09-01T12:00:00Z."
            )
        return parsed.astimezone(timezone.utc)

    def _filter_system_records_as_of(
        self,
        records: Any,
        cutoff: datetime,
    ) -> tuple[List[Dict[str, Any]], List[int]]:
        if not isinstance(records, list):
            raise CommandError("SystemStatusNews must be a JSON list.")

        retained: List[Dict[str, Any]] = []
        excluded_nids: List[int] = []
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise CommandError(
                    f"SystemStatusNews record {index} must be a JSON object."
                )

            try:
                nid = int(_nid(record))
            except (TypeError, ValueError) as exc:
                raise CommandError(
                    f"SystemStatusNews record {index} requires a numeric Drupal nid "
                    "for cutoff reporting."
                ) from exc

            start = _as_dt(record.get("start_datetime"))
            if start is None:
                raise CommandError(
                    f"SystemStatusNews nid={nid} requires a valid start_datetime "
                    "for --system-news-as-of filtering."
                )
            raw_end = record.get("end_datetime")
            end = _as_dt(raw_end)
            if raw_end and end is None:
                raise CommandError(
                    f"SystemStatusNews nid={nid} has an invalid end_datetime for "
                    "--system-news-as-of filtering."
                )

            is_current = start <= cutoff and (end is None or end >= cutoff)
            is_future = start >= cutoff
            if is_current or is_future:
                retained.append(record)
            else:
                excluded_nids.append(nid)

        return retained, sorted(excluded_nids)

    def _validate_replace_target(
        self,
        confirm_database: Optional[str],
        confirm_host: Optional[str],
    ) -> None:
        if not confirm_database or not confirm_host:
            raise CommandError(
                "--replace requires both --confirm-database and --confirm-host."
            )

        configured = settings.DATABASES["default"]
        actual_database = str(configured.get("NAME") or "")
        actual_host = str(configured.get("HOST") or "")

        if str(confirm_database) != actual_database:
            raise CommandError(
                "Refusing replacement: configured database does not match "
                f"--confirm-database ({actual_database!r} != {confirm_database!r})."
            )
        if str(confirm_host) != actual_host:
            raise CommandError(
                "Refusing replacement: configured write host does not match "
                f"--confirm-host ({actual_host!r} != {confirm_host!r})."
            )

    def _validated_source_ids(
        self,
        records: Any,
        feed_name: str,
        allow_empty: bool = False,
    ) -> set[int]:
        if not isinstance(records, list):
            raise CommandError(f"Replacement requires a {feed_name} list.")
        if not records and not allow_empty:
            raise CommandError(
                f"Replacement requires a nonempty {feed_name} list."
            )

        ids: set[int] = set()
        for index, record in enumerate(records):
            if not isinstance(record, dict):
                raise CommandError(
                    f"{feed_name} record {index} must be a JSON object."
                )
            raw_id = (record.get("source_metadata", {}) or {}).get("drupal_nid")
            if isinstance(raw_id, bool):
                raise CommandError(
                    f"{feed_name} record {index} has invalid Drupal nid {raw_id!r}."
                )
            try:
                stable_id = int(raw_id)
            except (TypeError, ValueError):
                raise CommandError(
                    f"{feed_name} record {index} has invalid Drupal nid {raw_id!r}."
                )
            if stable_id <= 0:
                raise CommandError(
                    f"{feed_name} record {index} has nonpositive Drupal nid {stable_id}."
                )
            if stable_id in ids:
                raise CommandError(
                    f"{feed_name} contains duplicate Drupal nid {stable_id}."
                )
            ids.add(stable_id)
        return ids

    def _validate_replacement(
        self,
        expected_system_ids: set[int],
        expected_integration_ids: set[int],
        system_records: List[Dict[str, Any]],
        integration_records: List[Dict[str, Any]],
        suppress_notifications: bool,
    ) -> None:
        actual_system_ids = set(
            SystemStatusNews.objects.values_list("outage_id", flat=True)
        )
        actual_integration_ids = set(
            IntegrationNews.objects.values_list("integration_news_id", flat=True)
        )

        if actual_system_ids != expected_system_ids:
            raise CommandError(
                "Replacement validation failed for SystemStatusNews stable IDs."
            )
        if actual_integration_ids != expected_integration_ids:
            raise CommandError(
                "Replacement validation failed for IntegrationNews stable IDs."
            )

        system_by_id = {
            item.outage_id: item
            for item in SystemStatusNews.objects.prefetch_related(
                "affected_infrastructure_items"
            )
        }
        for record in system_records:
            stable_id = int(_nid(record))
            obj = system_by_id[stable_id]
            expected_fields = {
                "subject": record.get("subject") or "Untitled",
                "content": record.get("content") or "",
                "infrastructure_news_type": record.get("infrastructure_news_type")
                or "outage_full",
                "affected_infrastructure": record.get("affected_infrastructure") or "",
                "start_datetime": _as_dt(record.get("start_datetime")),
                "end_datetime": _as_dt(record.get("end_datetime")),
                "send_email": False
                if suppress_notifications
                else bool(record.get("send_email", False)),
                "post_to_slack": False
                if suppress_notifications
                else bool(record.get("post_to_slack", False)),
                "is_active": bool(record.get("is_active", True)),
                "status": record.get("status") or "published",
                "review_comments": _provenance_tag(record),
            }
            for field_name, expected in expected_fields.items():
                if getattr(obj, field_name) != expected:
                    raise CommandError(
                        "Replacement validation failed for SystemStatusNews "
                        f"nid={stable_id} field {field_name}."
                    )

            expected_resources = {
                str(node.get("resource_id"))
                for node in (
                    (record.get("source_metadata", {}) or {}).get(
                        "affected_infrastructure_nodes"
                    )
                    or []
                )
                if isinstance(node, dict) and node.get("resource_id")
            }
            if not expected_resources and obj.affected_infrastructure:
                expected_resources = {
                    value.strip()
                    for value in obj.affected_infrastructure.split(",")
                    if value.strip()
                }
            actual_resources = set(
                obj.affected_infrastructure_items.values_list(
                    "info_resourceid", flat=True
                )
            )
            if actual_resources != expected_resources:
                raise CommandError(
                    "Replacement validation failed for SystemStatusNews "
                    f"nid={stable_id} affected infrastructure relationships."
                )

        integration_by_id = {
            item.integration_news_id: item
            for item in IntegrationNews.objects.prefetch_related("affected_elements")
        }
        for record in integration_records:
            stable_id = int(_nid(record))
            obj = integration_by_id[stable_id]
            expected_codes = record.get("affected_elements")
            if expected_codes is None:
                primary = record.get("affected_element")
                expected_codes = [str(primary)] if primary else []
            expected_fields = {
                "title": record.get("title") or "Untitled",
                "content": record.get("content") or "",
                "news_type": record.get("news_type") or "",
                "affected_element": (
                    str(expected_codes[0]) if len(expected_codes) == 1 else ""
                ),
                "effective_date": _as_date(record.get("effective_date")),
                "expiration_date": _as_date(record.get("expiration_date")),
                "is_active": bool(record.get("is_active", True)),
                "status": record.get("status") or "published",
                "review_comments": _provenance_tag(record),
            }
            for field_name, expected in expected_fields.items():
                if getattr(obj, field_name) != expected:
                    raise CommandError(
                        "Replacement validation failed for IntegrationNews "
                        f"nid={stable_id} field {field_name}."
                    )
            actual_codes = set(
                obj.affected_elements.values_list("code", flat=True)
            )
            if actual_codes != set(expected_codes):
                raise CommandError(
                    "Replacement validation failed for IntegrationNews "
                    f"nid={stable_id} affected element relationships."
                )

    def _resolve_import_user(
        self,
        username: str,
        create_missing: bool,
        dry_run: bool,
        result: ImportResult,
    ) -> User:
        user = User.objects.filter(username=username).first()
        if user:
            return user

        if dry_run:
            fallback = User.objects.order_by("id").first()
            if fallback:
                result.add_warning(
                    f"Import user '{username}' not found; dry-run used fallback user id={fallback.id}."
                )
                return fallback
            raise CommandError(
                "No Django users exist to simulate author assignment in dry-run."
            )

        if create_missing:
            user = User.objects.create_user(
                username=username,
                email=f"{username}@local.invalid",
                password=User.objects.make_random_password(),
                is_active=True,
            )
            result.add_warning(f"Created missing import user '{username}'.")
            return user

        raise CommandError(
            f"Import user '{username}' does not exist. "
            "Re-run with --create-import-user or set --import-user."
        )

    def _ensure_integration_elements(
        self,
        dry_run: bool,
        result: ImportResult,
    ) -> Dict[str, IntegrationElement]:
        elements: Dict[str, IntegrationElement] = {
            element.code: element for element in IntegrationElement.objects.all()
        }
        for code, label in IntegrationNews.AFFECTED_ELEMENTS:
            existing = elements.get(code)
            if existing:
                if existing.label != label:
                    existing.label = label
                    result.integration_elements_updated += 1
                    if not dry_run:
                        existing.save(update_fields=["label"])
                continue
            element = IntegrationElement(code=code, label=label)
            if not dry_run:
                element.save()
            elements[code] = element
            result.integration_elements_created += 1
        return elements

    def _find_existing_system(self, record: Dict[str, Any]) -> Optional[SystemStatusNews]:
        nid_raw = _nid(record)
        if nid_raw != "unknown":
            try:
                by_id = SystemStatusNews.objects.filter(outage_id=int(nid_raw)).first()
                if by_id:
                    return by_id
            except (ValueError, TypeError):
                pass

        # Backward compatibility for earlier imports that stored Drupal provenance
        legacy = SystemStatusNews.objects.filter(
            review_comments__contains=f"[drupal_nid:{nid_raw};"
        ).first()
        if legacy:
            return legacy

        return SystemStatusNews.objects.filter(
            subject=(record.get("subject") or "Untitled"),
            content=(record.get("content") or ""),
            start_datetime=_as_dt(record.get("start_datetime")),
            end_datetime=_as_dt(record.get("end_datetime")),
            infrastructure_news_type=(record.get("infrastructure_news_type") or "outage_full"),
        ).first()

    def _find_existing_integration(self, record: Dict[str, Any]) -> Optional[IntegrationNews]:
        nid_raw = _nid(record)
        if nid_raw != "unknown":
            try:
                by_id = IntegrationNews.objects.filter(integration_news_id=int(nid_raw)).first()
                if by_id:
                    return by_id
            except (ValueError, TypeError):
                pass

        # Backward compatibility for earlier imports that stored Drupal provenance
        legacy = IntegrationNews.objects.filter(
            review_comments__contains=f"[drupal_nid:{nid_raw};"
        ).first()
        if legacy:
            return legacy

        return IntegrationNews.objects.filter(
            title=(record.get("title") or "Untitled"),
            content=(record.get("content") or ""),
            news_type=(record.get("news_type") or ""),
            effective_date=_as_date(record.get("effective_date")),
            expiration_date=_as_date(record.get("expiration_date")),
        ).first()

    def _import_system_record(
        self,
        record: Dict[str, Any],
        import_user: User,
        dry_run: bool,
        result: ImportResult,
        force_create: bool = False,
        suppress_notifications: bool = False,
    ) -> None:
        existing = None if force_create else self._find_existing_system(record)
        creating = existing is None
        obj = existing or SystemStatusNews(author=import_user)

        obj.subject = record.get("subject") or "Untitled"
        obj.content = record.get("content") or ""
        obj.infrastructure_news_type = record.get("infrastructure_news_type") or "outage_full"
        obj.affected_infrastructure = record.get("affected_infrastructure") or ""
        obj.start_datetime = _as_dt(record.get("start_datetime"))
        obj.end_datetime = _as_dt(record.get("end_datetime"))
        obj.send_email = False if suppress_notifications else bool(record.get("send_email", False))
        obj.post_to_slack = False if suppress_notifications else bool(record.get("post_to_slack", False))
        obj.is_active = bool(record.get("is_active", True))
        obj.status = record.get("status") or "published"
        obj.review_comments = _provenance_tag(record)
        if obj.status == "published":
            obj.published_at = _as_dt((record.get("source_metadata", {}) or {}).get("drupal_created_at"))

        nid_raw = _nid(record)
        if nid_raw != "unknown" and obj.outage_id is None:
            try:
                obj.outage_id = int(nid_raw)
            except (ValueError, TypeError):
                pass

        try:
            obj.full_clean(validate_unique=False, validate_constraints=False)
        except ValidationError as exc:
            raise CommandError(
                f"SystemStatusNews nid={_nid(record)} failed model validation: "
                f"{exc.message_dict}"
            ) from exc

        if not dry_run:
            obj.save()

        if creating:
            result.created_system += 1
        else:
            result.updated_system += 1

        related_nodes = (record.get("source_metadata", {}) or {}).get("affected_infrastructure_nodes") or []
        resource_ids = []
        for node in related_nodes:
            if isinstance(node, dict):
                rid = node.get("resource_id")
                if rid:
                    resource_ids.append(str(rid))

        if not resource_ids and obj.affected_infrastructure:
            resource_ids = [item.strip() for item in obj.affected_infrastructure.split(",") if item.strip()]

        matched_infra = list(CiderInfrastructure.objects.filter(info_resourceid__in=resource_ids))
        matched_counts: Dict[str, int] = {}
        for infrastructure in matched_infra:
            matched_counts[infrastructure.info_resourceid] = (
                matched_counts.get(infrastructure.info_resourceid, 0) + 1
            )
        duplicate_ids = sorted(
            resource_id
            for resource_id, count in matched_counts.items()
            if count > 1
        )
        if duplicate_ids:
            result.add_warning(
                f"SystemStatusNews nid={_nid(record)} has non-unique CIDER matches: "
                f"{duplicate_ids}"
            )
        matched_ids = {infra.info_resourceid for infra in matched_infra}
        missing_ids = sorted(set(resource_ids) - matched_ids)
        if missing_ids:
            result.add_warning(
                f"SystemStatusNews nid={_nid(record)} has unmatched infrastructure IDs: {missing_ids}"
            )

        if not resource_ids:
            result.system_na_infrastructure += 1

        if not dry_run and obj.pk:
            obj.affected_infrastructure_items.set(matched_infra)

    def _import_integration_record(
        self,
        record: Dict[str, Any],
        import_user: User,
        integration_elements: Dict[str, IntegrationElement],
        allow_na_affected_element: bool,
        dry_run: bool,
        result: ImportResult,
        force_create: bool = False,
    ) -> None:
        existing = None if force_create else self._find_existing_integration(record)
        creating = existing is None
        obj = existing or IntegrationNews(author=import_user)

        obj.title = record.get("title") or "Untitled"
        obj.content = record.get("content") or ""
        obj.news_type = record.get("news_type") or ""
        obj.effective_date = _as_date(record.get("effective_date"))
        obj.expiration_date = _as_date(record.get("expiration_date"))
        obj.is_active = bool(record.get("is_active", True))
        obj.status = record.get("status") or "published"
        obj.review_comments = _provenance_tag(record)
        if obj.status == "published":
            obj.published_at = _as_dt((record.get("source_metadata", {}) or {}).get("drupal_created_at"))

        nid_raw = _nid(record)
        if nid_raw != "unknown" and obj.integration_news_id is None:
            try:
                obj.integration_news_id = int(nid_raw)
            except (ValueError, TypeError):
                pass

        selected_codes: List[str] = []
        explicit_codes = record.get("affected_elements")
        primary_code = record.get("affected_element")
        candidates = record.get("affected_element_candidates", []) or []
        unresolved = "affected_element_unresolved" in (record.get("migration_flags") or [])

        if explicit_codes is not None:
            if not isinstance(explicit_codes, list):
                raise CommandError(
                    f"IntegrationNews nid={_nid(record)} affected_elements must be a list."
                )
            selected_codes = [str(code) for code in explicit_codes]
            if len(selected_codes) != len(set(selected_codes)):
                raise CommandError(
                    f"IntegrationNews nid={_nid(record)} contains duplicate affected elements."
                )
            obj.affected_element = selected_codes[0] if len(selected_codes) == 1 else ""
            if not selected_codes:
                result.integration_na_element += 1
        elif primary_code:
            selected_codes = [str(primary_code)]
            obj.affected_element = str(primary_code)
        elif unresolved:
            if allow_na_affected_element:
                result.unresolved_allowed_na += 1
                obj.affected_element = ""
                result.integration_na_element += 1
                result.add_warning(
                    f"IntegrationNews nid={_nid(record)} ambiguous candidates={candidates}; imported as N/A."
                )
            else:
                raise CommandError(
                    f"IntegrationNews nid={_nid(record)} unresolved affected_element and "
                    "--allow-na-affected-element is disabled."
                )
        else:
            obj.affected_element = ""
            result.integration_na_element += 1

        try:
            obj.full_clean(validate_unique=False, validate_constraints=False)
        except ValidationError as exc:
            raise CommandError(
                f"IntegrationNews nid={_nid(record)} failed model validation: "
                f"{exc.message_dict}"
            ) from exc

        if not dry_run:
            obj.save()

        if creating:
            result.created_integration += 1
        else:
            result.updated_integration += 1

        m2m_elements: List[IntegrationElement] = []
        for code in selected_codes:
            element = integration_elements.get(code)
            if element is None:
                result.add_warning(
                    f"IntegrationNews nid={_nid(record)} references unknown integration code '{code}'."
                )
                continue
            m2m_elements.append(element)

        if not dry_run and obj.pk:
            obj.affected_elements.set(m2m_elements)

    def _write_report(
        self,
        report_path: Path,
        result: ImportResult,
        dry_run: bool,
        input_path: Path,
        source_kind: str,
        source_sha256: str,
    ) -> None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Drupal News Import Run Report",
            "",
            f"- Run time (UTC): `{datetime.now(timezone.utc).isoformat()}`",
            f"- Mode: `{'dry-run' if dry_run else 'import'}`",
            f"- Source kind: `{source_kind}`",
            f"- Input file: `{input_path}`",
            f"- Input SHA-256: `{source_sha256}`",
            f"- Python executable: `{sys.executable}`",
            f"- Target database: `{settings.DATABASES['default'].get('NAME') or ''}`",
            f"- Target write host: `{settings.DATABASES['default'].get('HOST') or ''}`",
            "- Import plan file: "
            + (f"`{result.plan_file}`" if result.plan_file else "None"),
            "- Import plan SHA-256: "
            + (f"`{result.plan_sha256}`" if result.plan_sha256 else "None"),
            "",
            "## Summary",
            "",
            f"- Total staged records: `{result.total_records}`",
            f"- `SystemStatusNews` staged: `{result.system_records}`",
            f"- `IntegrationNews` staged: `{result.integration_records}`",
            f"- Expected infrastructure relationships: `{result.system_relationships}`",
            f"- Expected integration-element relationships: `{result.integration_relationships}`",
            f"- `IntegrationElement` rows created: `{result.integration_elements_created}`",
            f"- `IntegrationElement` labels updated: `{result.integration_elements_updated}`",
            "",
            "## Explicit Source Adjustments",
            "",
            "- Infrastructure News cutoff: "
            + (f"`{result.system_news_as_of}`" if result.system_news_as_of else "None"),
            "- Cutoff-excluded past `SystemStatusNews` Drupal nids: "
            + (
                ", ".join(
                    f"`{nid}`" for nid in result.cutoff_excluded_system_nids
                )
                if result.cutoff_excluded_system_nids
                else "None"
            ),
            "- Excluded `SystemStatusNews` Drupal nids: "
            + (
                ", ".join(f"`{nid}`" for nid in result.excluded_system_nids)
                if result.excluded_system_nids
                else "None"
            ),
            "- Applied exact-match corrections:",
        ]

        if result.source_corrections:
            lines.extend(
                [f"  - {correction}" for correction in result.source_corrections]
            )
        else:
            lines.append("  - None")

        lines.extend([
            "",
            "## Planned/Applied Changes",
            "",
            f"- `SystemStatusNews` deleted: `{result.deleted_system}`",
            f"- `IntegrationNews` deleted: `{result.deleted_integration}`",
            f"- `SystemStatusNews` created: `{result.created_system}`",
            f"- `SystemStatusNews` updated: `{result.updated_system}`",
            f"- `IntegrationNews` created: `{result.created_integration}`",
            f"- `IntegrationNews` updated: `{result.updated_integration}`",
            "",
            "## N/A Handling",
            "",
            f"- `SystemStatusNews` records with no mapped infrastructure (`N/A`): `{result.system_na_infrastructure}`",
            f"- `IntegrationNews` records with no affected element (`N/A`): `{result.integration_na_element}`",
            f"- Ambiguous integration mappings accepted as `N/A`: `{result.unresolved_allowed_na}`",
            "",
            "## Warnings",
            "",
        ])

        if result.warnings:
            lines.extend([f"- {warning}" for warning in result.warnings])
        else:
            lines.append("- None")

        lines.extend(["", "## Errors", ""])
        if result.errors:
            lines.extend([f"- {error}" for error in result.errors])
        else:
            lines.append("- None")

        lines.append("")
        report_path.write_text("\n".join(lines), encoding="utf-8")

    def _emit_summary(self, result: ImportResult, dry_run: bool, report_path: Path) -> None:
        mode = "DRY RUN" if dry_run else "IMPORT"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS(f"{mode} COMPLETE"))
        self.stdout.write(
            f"Deleted -> System: {result.deleted_system}, "
            f"Integration: {result.deleted_integration}"
        )
        self.stdout.write(
            f"Created/Updated -> System: {result.created_system}/{result.updated_system}, "
            f"Integration: {result.created_integration}/{result.updated_integration}"
        )
        self.stdout.write(
            f"N/A -> infrastructure: {result.system_na_infrastructure}, "
            f"integration element: {result.integration_na_element}"
        )
        self.stdout.write(
            "Source adjustments -> excluded system nids: "
            f"{result.excluded_system_nids or 'none'}, exact corrections: "
            f"{len(result.source_corrections)}"
        )
        self.stdout.write(
            "System news cutoff -> as of: "
            f"{result.system_news_as_of or 'none'}, excluded past nids: "
            f"{result.cutoff_excluded_system_nids or 'none'}"
        )
        self.stdout.write(f"Warnings: {len(result.warnings)}; Errors: {len(result.errors)}")
        if result.plan_file:
            self.stdout.write(
                f"Import plan: {result.plan_file} (SHA-256: {result.plan_sha256})"
            )
        self.stdout.write(f"Report: {report_path}")
