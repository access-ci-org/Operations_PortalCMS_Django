"""Import both Drupal news feeds from normalized JSON or a raw MySQL dump.

The raw-dump path is a guarded, atomic, one-time cutover workflow designed for
repeatable rehearsals before the final Drupal-to-Django replacement.
"""
from __future__ import annotations

import json
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


@dataclass
class ImportResult:
    total_records: int = 0
    system_records: int = 0
    integration_records: int = 0
    system_relationships: int = 0
    integration_relationships: int = 0
    integration_elements_created: int = 0
    integration_elements_updated: int = 0
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
                "Raw-dump imports require --replace and either --dry-run or --apply."
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
            help="Permit a --replace operation to write. Omit for normal dry-run planning.",
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
                "Expected SHA-256 of the source file. Required for --apply so the "
                "reviewed dry-run input and write input are provably identical."
            ),
        )
        parser.add_argument(
            "--confirm-system-count",
            type=int,
            help="Expected SystemStatusNews source count for a write-enabled replacement.",
        )
        parser.add_argument(
            "--confirm-integration-count",
            type=int,
            help="Expected IntegrationNews source count for a write-enabled replacement.",
        )
        parser.add_argument(
            "--suppress-notifications",
            action="store_true",
            help="Force imported infrastructure-news email and Slack flags off.",
        )

    def handle(self, *args, **options):
        mysql_dump = options.get("mysql_dump")
        input_path = Path(mysql_dump or options.get("input") or DEFAULT_INPUT)
        source_kind = "mysql-dump" if mysql_dump else "normalized-json"
        report_path = Path(options["report_file"])
        dry_run = bool(options["dry_run"])
        strict = bool(options["strict"])
        replace = bool(options["replace"])
        apply = bool(options["apply"])

        if apply and not replace:
            raise CommandError("--apply is only valid with --replace.")
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
            if dry_run and apply:
                raise CommandError("Choose either --dry-run or --apply, not both.")
            if not dry_run and not apply:
                raise CommandError(
                    "A replacement write requires --apply. Use --dry-run to review the plan first."
                )

        if apply and not options.get("confirm_source_sha256"):
            raise CommandError("--apply requires --confirm-source-sha256.")
        if mysql_dump and apply and not strict:
            raise CommandError("A raw-dump --apply requires --strict.")

        if not input_path.exists():
            raise CommandError(f"Input file does not exist: {input_path}")

        source_sha256 = sha256_file(input_path)
        confirmed_sha256 = options.get("confirm_source_sha256")
        if confirmed_sha256 and confirmed_sha256.lower() != source_sha256:
            raise CommandError(
                "Refusing import: source SHA-256 does not match "
                "--confirm-source-sha256."
            )

        source_warnings: List[str] = []
        result = ImportResult()
        if mysql_dump:
            try:
                parsed_dump = parse_drupal_news_dump(
                    input_path,
                    infrastructure_type_choices=SystemStatusNews.INFRASTRUCTURE_NEWS_TYPES,
                    integration_type_choices=IntegrationNews.INTEGRATION_NEWS_TYPES,
                    integration_element_choices=IntegrationNews.AFFECTED_ELEMENTS,
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
        else:
            payload = json.loads(input_path.read_text(encoding="utf-8"))
        system_records = payload.get("SystemStatusNews", [])
        integration_records = payload.get("IntegrationNews", [])

        if apply:
            expected_system_count = options.get("confirm_system_count")
            expected_integration_count = options.get("confirm_integration_count")
            if expected_system_count is None or expected_integration_count is None:
                raise CommandError(
                    "--apply requires --confirm-system-count and "
                    "--confirm-integration-count."
                )
            if expected_system_count != len(system_records):
                raise CommandError(
                    "Refusing import: SystemStatusNews source count does not match "
                    f"--confirm-system-count ({len(system_records)} != "
                    f"{expected_system_count})."
                )
            if expected_integration_count != len(integration_records):
                raise CommandError(
                    "Refusing import: IntegrationNews source count does not match "
                    f"--confirm-integration-count ({len(integration_records)} != "
                    f"{expected_integration_count})."
                )

        expected_system_ids: set[int] = set()
        expected_integration_ids: set[int] = set()
        if replace:
            expected_system_ids = self._validated_source_ids(
                records=system_records,
                feed_name="SystemStatusNews",
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

        self._write_report(
            report_path=report_path,
            result=result,
            dry_run=dry_run,
            input_path=input_path,
            source_kind=source_kind,
            source_sha256=source_sha256,
        )
        self._emit_summary(result=result, dry_run=dry_run, report_path=report_path)

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
    ) -> set[int]:
        if not isinstance(records, list) or not records:
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
        ]

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
        self.stdout.write(f"Warnings: {len(result.warnings)}; Errors: {len(result.errors)}")
        self.stdout.write(f"Report: {report_path}")
