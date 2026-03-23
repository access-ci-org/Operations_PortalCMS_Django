"""
Import normalized Drupal news staging JSON into Django news models.

Designed to support a safe dry-run workflow before writing data.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_date, parse_datetime

from operations_portalcms_django.models import (
    CiderInfrastructure,
    IntegrationElement,
    IntegrationNews,
    SystemStatusNews,
)


DEFAULT_INPUT = Path("database/drupal_backups/generated/drupal_news_normalized_for_django.json")
DEFAULT_REPORT = Path("database/drupal_backups/generated/drupal_news_import_dry_run.md")


@dataclass
class ImportResult:
    total_records: int = 0
    system_records: int = 0
    integration_records: int = 0
    created_system: int = 0
    updated_system: int = 0
    created_integration: int = 0
    updated_integration: int = 0
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
        "Import normalized Drupal news JSON into SystemStatusNews and IntegrationNews. "
        "Supports --dry-run and markdown reporting."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--input",
            default=str(DEFAULT_INPUT),
            help=f"Path to normalized combined JSON (default: {DEFAULT_INPUT})",
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

    def handle(self, *args, **options):
        input_path = Path(options["input"])
        report_path = Path(options["report_file"])
        dry_run = bool(options["dry_run"])
        strict = bool(options["strict"])

        if not input_path.exists():
            raise CommandError(f"Input file does not exist: {input_path}")

        payload = json.loads(input_path.read_text(encoding="utf-8"))
        system_records = payload.get("SystemStatusNews", [])
        integration_records = payload.get("IntegrationNews", [])

        self.stdout.write(f"Input: {input_path}")
        self.stdout.write(
            f"Records detected -> SystemStatusNews: {len(system_records)}, IntegrationNews: {len(integration_records)}"
        )

        result = ImportResult(
            total_records=len(system_records) + len(integration_records),
            system_records=len(system_records),
            integration_records=len(integration_records),
        )

        import_user = self._resolve_import_user(
            username=options["import_user"],
            create_missing=bool(options["create_import_user"]),
            dry_run=dry_run,
            result=result,
        )
        integration_elements = self._ensure_integration_elements(dry_run=dry_run)

        try:
            with transaction.atomic():
                for record in system_records:
                    self._import_system_record(
                        record=record,
                        import_user=import_user,
                        dry_run=dry_run,
                        result=result,
                    )
                for record in integration_records:
                    self._import_integration_record(
                        record=record,
                        import_user=import_user,
                        integration_elements=integration_elements,
                        allow_na_affected_element=bool(options["allow_na_affected_element"]),
                        dry_run=dry_run,
                        result=result,
                    )

                if dry_run:
                    # Ensure absolutely no writes in dry-run mode.
                    transaction.set_rollback(True)

            if strict and result.warnings:
                raise CommandError(
                    f"Strict mode enabled and warnings found ({len(result.warnings)}). "
                    "See report for details."
                )

        except Exception as exc:
            result.add_error(str(exc))
            self._write_report(
                report_path=report_path,
                result=result,
                dry_run=dry_run,
                input_path=input_path,
            )
            raise

        self._write_report(
            report_path=report_path,
            result=result,
            dry_run=dry_run,
            input_path=input_path,
        )
        self._emit_summary(result=result, dry_run=dry_run, report_path=report_path)

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

    def _ensure_integration_elements(self, dry_run: bool) -> Dict[str, IntegrationElement]:
        elements: Dict[str, IntegrationElement] = {
            element.code: element for element in IntegrationElement.objects.all()
        }
        for code, label in IntegrationNews.AFFECTED_ELEMENTS:
            if code in elements:
                continue
            element = IntegrationElement(code=code, label=label)
            if not dry_run:
                element.save()
            elements[code] = element
        return elements

    def _find_existing_system(self, record: Dict[str, Any]) -> Optional[SystemStatusNews]:
        # Backward compatibility for earlier imports that stored Drupal provenance
        legacy = SystemStatusNews.objects.filter(
            review_comments__contains=f"[drupal_nid:{_nid(record)};"
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
        # Backward compatibility for earlier imports that stored Drupal provenance
        legacy = IntegrationNews.objects.filter(
            review_comments__contains=f"[drupal_nid:{_nid(record)};"
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
    ) -> None:
        existing = self._find_existing_system(record)
        creating = existing is None
        obj = existing or SystemStatusNews(author=import_user)

        obj.subject = record.get("subject") or "Untitled"
        obj.content = record.get("content") or ""
        obj.infrastructure_news_type = record.get("infrastructure_news_type") or "outage_full"
        obj.affected_infrastructure = record.get("affected_infrastructure") or ""
        obj.start_datetime = _as_dt(record.get("start_datetime"))
        obj.end_datetime = _as_dt(record.get("end_datetime"))
        obj.send_email = bool(record.get("send_email", False))
        obj.post_to_slack = bool(record.get("post_to_slack", False))
        obj.is_active = bool(record.get("is_active", True))
        obj.status = record.get("status") or "published"
        obj.review_comments = _provenance_tag(record)
        if obj.status == "published":
            obj.published_at = _as_dt((record.get("source_metadata", {}) or {}).get("drupal_created_at"))

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
    ) -> None:
        existing = self._find_existing_integration(record)
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

        selected_codes: List[str] = []
        primary_code = record.get("affected_element")
        candidates = record.get("affected_element_candidates", []) or []
        unresolved = "affected_element_unresolved" in (record.get("migration_flags") or [])

        if primary_code:
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
    ) -> None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [
            "# Drupal News Import Run Report",
            "",
            f"- Run time (UTC): `{datetime.now(timezone.utc).isoformat()}`",
            f"- Mode: `{'dry-run' if dry_run else 'import'}`",
            f"- Input file: `{input_path}`",
            "",
            "## Summary",
            "",
            f"- Total staged records: `{result.total_records}`",
            f"- `SystemStatusNews` staged: `{result.system_records}`",
            f"- `IntegrationNews` staged: `{result.integration_records}`",
            "",
            "## Planned/Applied Changes",
            "",
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
            f"Created/Updated -> System: {result.created_system}/{result.updated_system}, "
            f"Integration: {result.created_integration}/{result.updated_integration}"
        )
        self.stdout.write(
            f"N/A -> infrastructure: {result.system_na_infrastructure}, "
            f"integration element: {result.integration_na_element}"
        )
        self.stdout.write(f"Warnings: {len(result.warnings)}; Errors: {len(result.errors)}")
        self.stdout.write(f"Report: {report_path}")
