"""
Management command to sync CIDER data from Operations API.

Default strategy:
- v2/access-active/ for full infrastructure records
- v2/access-active-groups/ for groups, organizations, and feature catalogs
"""
from __future__ import annotations

from collections import defaultdict

import requests
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.dateparse import parse_datetime

from operations_portalcms_django.models import (
    CiderFeatures,
    CiderGroups,
    CiderInfrastructure,
    CiderOrganizations,
)


class Command(BaseCommand):
    help = "Syncs CIDER data from Operations API (infrastructure, groups, organizations, features)"

    API_BASE = "https://operations-api.access-ci.org/wh2/cider"

    def add_arguments(self, parser):
        parser.add_argument(
            "--api-url",
            type=str,
            default=None,
            help="Override API base URL (default: https://operations-api.access-ci.org/wh2/cider)",
        )
        parser.add_argument(
            "--timeout",
            type=int,
            default=45,
            help="HTTP timeout in seconds (default: 45).",
        )
        parser.add_argument(
            "--group-prefix",
            type=str,
            default="",
            help=(
                "Optional filter for groups by info_groupid prefix (e.g. 'rp.'). "
                "Default empty = sync all active groups."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and process data but do not write database changes.",
        )
        parser.add_argument(
            "--skip-infrastructure",
            action="store_true",
            help="Skip infrastructure sync from /v2/access-active/.",
        )
        parser.add_argument(
            "--skip-groups-bundle",
            action="store_true",
            help="Skip group/org/feature sync from /v2/access-active-groups/.",
        )
        parser.add_argument(
            "--prune-stale-groups",
            action="store_true",
            help=(
                "Delete local CIDER groups that are not present in the fetched active_groups "
                "payload. Honors --dry-run and --group-prefix."
            ),
        )

    def handle(self, *args, **options):
        if options["api_url"]:
            self.API_BASE = options["api_url"]

        timeout = int(options["timeout"])
        group_prefix = str(options["group_prefix"] or "")
        dry_run = bool(options["dry_run"])
        skip_infrastructure = bool(options["skip_infrastructure"])
        skip_groups_bundle = bool(options["skip_groups_bundle"])
        prune_stale_groups = bool(options["prune_stale_groups"])

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("SYNCING CIDER DATA FROM API")
        self.stdout.write("=" * 70)
        self.stdout.write(f"Base URL: {self.API_BASE}")
        self.stdout.write(f"Mode: {'dry-run' if dry_run else 'write'}")
        self.stdout.write("")

        counts = defaultdict(int)

        try:
            with transaction.atomic():
                if not skip_infrastructure:
                    self.sync_infrastructure(timeout=timeout, dry_run=dry_run, counts=counts)
                if not skip_groups_bundle:
                    self.sync_groups_bundle(
                        timeout=timeout,
                        dry_run=dry_run,
                        group_prefix=group_prefix,
                        prune_stale_groups=prune_stale_groups,
                        counts=counts,
                    )
                if dry_run:
                    transaction.set_rollback(True)
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f"✗ Sync failed: {e}"))
            return

        self.stdout.write("\n" + "=" * 70)
        self.stdout.write(self.style.SUCCESS("✓ CIDER Data Sync Complete"))
        self.stdout.write("=" * 70)
        self.stdout.write("Summary:")
        for key in sorted(counts):
            self.stdout.write(f"  - {key}: {counts[key]}")
        self.stdout.write("")

    def fetch_json(self, url: str, timeout: int):
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        return response.json()

    def clip(self, value, length: int) -> str:
        if value is None:
            return ""
        text = str(value)
        return text[:length]

    def sync_infrastructure(self, timeout: int, dry_run: bool, counts) -> None:
        self.stdout.write("--- Syncing Infrastructure (/v2/access-active/) ---")
        url = f"{self.API_BASE}/v2/access-active/"
        data = self.fetch_json(url, timeout=timeout)
        resources = data.get("results", [])
        self.stdout.write(f"Fetched resources: {len(resources)}")

        for resource in resources:
            resource_id = resource.get("cider_resource_id")
            if resource_id is None:
                counts["infrastructure_skipped_missing_id"] += 1
                continue

            updated_at_raw = resource.get("updated_at")
            updated_at = parse_datetime(updated_at_raw) if updated_at_raw else None
            defaults = {
                "cider_type": self.clip(resource.get("cider_type"), 16),
                "info_resourceid": self.clip(resource.get("info_resourceid"), 40),
                "info_siteid": self.clip(resource.get("info_siteid"), 40),
                "resource_descriptive_name": self.clip(resource.get("resource_descriptive_name"), 120),
                "resource_description": self.clip(resource.get("resource_description"), 4000),
                "resource_status": resource.get("resource_status"),
                "current_statuses": self.clip(resource.get("fixed_status") or resource.get("latest_status"), 64),
                "latest_status": self.clip(resource.get("latest_status"), 32),
                "latest_status_begin": resource.get("latest_status_begin"),
                "latest_status_end": resource.get("latest_status_end"),
                "parent_resource": resource.get("parent_resource"),
                "recommended_use": self.clip(resource.get("recommended_use"), 4000),
                "access_description": self.clip(resource.get("access_description"), 4000),
                "project_affiliation": self.clip(resource.get("project_affiliation"), 64),
                "provider_level": self.clip(resource.get("provider_level"), 16),
                "protected_attributes": resource.get("protected_attributes"),
                "other_attributes": {
                    "short_name": resource.get("short_name"),
                    "organization_id": resource.get("organization_id"),
                    "organization_name": resource.get("organization_name"),
                    "organization_url": resource.get("organization_url"),
                    "organization_logo_url": resource.get("organization_logo_url"),
                    "cider_view_url": resource.get("cider_view_url"),
                    "cider_data_url": resource.get("cider_data_url"),
                },
                "updated_at": updated_at,
            }

            if dry_run:
                exists = CiderInfrastructure.objects.filter(cider_resource_id=resource_id).exists()
                if exists:
                    counts["infrastructure_would_update"] += 1
                else:
                    counts["infrastructure_would_create"] += 1
                continue

            _, created = CiderInfrastructure.objects.update_or_create(
                cider_resource_id=resource_id,
                defaults=defaults,
            )
            if created:
                counts["infrastructure_created"] += 1
            else:
                counts["infrastructure_updated"] += 1

    def sync_groups_bundle(
        self,
        timeout: int,
        dry_run: bool,
        group_prefix: str,
        prune_stale_groups: bool,
        counts,
    ) -> None:
        self.stdout.write("--- Syncing Groups Bundle (/v2/access-active-groups/) ---")
        url = f"{self.API_BASE}/v2/access-active-groups/"
        data = self.fetch_json(url, timeout=timeout)
        results = data.get("results", {})
        active_groups = results.get("active_groups", [])
        organizations = results.get("organizations", [])
        feature_categories = results.get("feature_categories", [])
        features = results.get("features", [])

        self.stdout.write(
            f"Fetched groups={len(active_groups)}, orgs={len(organizations)}, "
            f"feature_categories={len(feature_categories)}, features={len(features)}"
        )

        # Sync groups
        source_group_ids = set()
        for group in active_groups:
            info_groupid = group.get("info_groupid", "")
            if group_prefix and not info_groupid.startswith(group_prefix):
                continue

            group_id = group.get("group_id")
            if group_id is None:
                counts["groups_skipped_missing_id"] += 1
                continue
            source_group_ids.add(group_id)

            defaults = {
                "info_groupid": self.clip(info_groupid, 40),
                "group_descriptive_name": self.clip(group.get("group_descriptive_name"), 120),
                "group_description": self.clip(group.get("group_description"), 4000),
                "group_logo_url": self.clip(group.get("group_logo_url"), 320),
                "group_types": group.get("group_types", []),
                "info_resourceids": group.get("rollup_info_resourceids", []),
                "other_attributes": {
                    "rollup_feature_ids": group.get("rollup_feature_ids", []),
                    "rollup_organization_ids": group.get("rollup_organization_ids", []),
                    "rollup_badge_ids": group.get("rollup_badge_ids", []),
                    "source_other_attributes": group.get("other_attributes", {}),
                },
            }

            if dry_run:
                exists = CiderGroups.objects.filter(group_id=group_id).exists()
                if exists:
                    counts["groups_would_update"] += 1
                else:
                    counts["groups_would_create"] += 1
                continue

            _, created = CiderGroups.objects.update_or_create(group_id=group_id, defaults=defaults)
            if created:
                counts["groups_created"] += 1
            else:
                counts["groups_updated"] += 1

        if prune_stale_groups:
            if not source_group_ids:
                raise CommandError(
                    "Refusing to prune stale CIDER groups because no source group IDs were processed."
                )

            stale_groups = CiderGroups.objects.exclude(group_id__in=source_group_ids)
            if group_prefix:
                stale_groups = stale_groups.filter(info_groupid__startswith=group_prefix)
            stale_count = stale_groups.count()

            if dry_run:
                counts["groups_would_delete"] += stale_count
            else:
                stale_groups.delete()
                counts["groups_deleted"] += stale_count

        # Sync organizations
        for org in organizations:
            organization_id = org.get("organization_id")
            if organization_id is None:
                counts["organizations_skipped_missing_id"] += 1
                continue

            defaults = {
                "organization_name": self.clip(org.get("organization_name"), 120),
                "organization_abbrev": self.clip(
                    org.get("organization_abbrev") or org.get("organization_abbreviation"), 20
                ),
                "organization_url": self.clip(org.get("organization_url"), 320),
                "other_attributes": {
                    "organization_code": org.get("organization_code"),
                    "organization_logo_url": org.get("organization_logo_url"),
                    "external_organization_id": org.get("external_organization_id"),
                    "external_organization_id_type": org.get("external_organization_id_type"),
                    "city": org.get("city"),
                    "state": org.get("state"),
                    "country": org.get("country"),
                },
            }

            if dry_run:
                exists = CiderOrganizations.objects.filter(organization_id=organization_id).exists()
                if exists:
                    counts["organizations_would_update"] += 1
                else:
                    counts["organizations_would_create"] += 1
                continue

            _, created = CiderOrganizations.objects.update_or_create(
                organization_id=organization_id,
                defaults=defaults,
            )
            if created:
                counts["organizations_created"] += 1
            else:
                counts["organizations_updated"] += 1

        # Sync feature catalogs
        feature_map = defaultdict(list)
        for feature in features:
            category_id = feature.get("feature_category_id")
            if category_id is None:
                continue
            feature_map[category_id].append(feature)

        for category in feature_categories:
            category_id = category.get("feature_category_id")
            if category_id is None:
                counts["feature_categories_skipped_missing_id"] += 1
                continue

            defaults = {
                "feature_category_name": self.clip(category.get("feature_category_name"), 120),
                "feature_category_description": self.clip(
                    category.get("feature_category_description"), 4000
                ),
                "feature_category_types": category.get("feature_category_types", []),
                "features": feature_map.get(category_id, []),
                "other_attributes": {},
            }

            if dry_run:
                exists = CiderFeatures.objects.filter(feature_category_id=category_id).exists()
                if exists:
                    counts["feature_categories_would_update"] += 1
                else:
                    counts["feature_categories_would_create"] += 1
                continue

            _, created = CiderFeatures.objects.update_or_create(
                feature_category_id=category_id,
                defaults=defaults,
            )
            if created:
                counts["feature_categories_created"] += 1
            else:
                counts["feature_categories_updated"] += 1
