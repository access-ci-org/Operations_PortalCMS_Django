"""Transfer legacy Text plugin permissions to the supported app label."""

from django.contrib.auth.models import Group, Permission
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction


LEGACY_APP_LABEL = "djangocms_text_ckeditor"
CURRENT_APP_LABEL = "djangocms_text"
TEXT_PERMISSION_CODENAMES = (
    "add_text",
    "change_text",
    "delete_text",
    "view_text",
)


class Command(BaseCommand):
    help = (
        "Copy legacy group-based Text plugin permissions to djangocms_text "
        "without changing group membership or removing legacy permissions."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report permission additions without writing them.",
        )

    def handle(self, *args, **options):
        permission_pairs = self._permission_pairs()
        group_additions = self._group_additions(permission_pairs)
        direct_user_grants = self._direct_user_grant_count(permission_pairs)

        self.stdout.write(
            "Text plugin permission transfer: "
            f"{len(group_additions)} group grant(s), "
            f"{direct_user_grants} legacy direct user grant(s) not transferred"
        )
        if direct_user_grants:
            self.stdout.write(self.style.WARNING(
                "Direct user permissions are not transferred; assign those "
                "users to an appropriate Django group."
            ))
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("DRY RUN: no database changes"))
            return

        with transaction.atomic():
            for group, permission in group_additions:
                group.permissions.add(permission)

        self.stdout.write(self.style.SUCCESS("Text plugin permissions transferred."))

    def _permission_pairs(self):
        pairs = []
        missing = []
        for codename in TEXT_PERMISSION_CODENAMES:
            legacy = Permission.objects.filter(
                content_type__app_label=LEGACY_APP_LABEL,
                content_type__model="text",
                codename=codename,
            ).first()
            current = Permission.objects.filter(
                content_type__app_label=CURRENT_APP_LABEL,
                content_type__model="text",
                codename=codename,
            ).first()
            if current is None:
                missing.append(f"{CURRENT_APP_LABEL}.text.{codename}")
            elif legacy is not None:
                pairs.append((legacy, current))
        if missing:
            raise CommandError(
                "Missing current Text permission(s); run the djangocms_text "
                "migrations first: " + ", ".join(missing)
            )
        return pairs

    @staticmethod
    def _group_additions(permission_pairs):
        additions = []
        for legacy, current in permission_pairs:
            for group in Group.objects.filter(permissions=legacy).order_by("pk"):
                if not group.permissions.filter(pk=current.pk).exists():
                    additions.append((group, current))
        return additions

    @staticmethod
    def _direct_user_grant_count(permission_pairs):
        return sum(legacy.user_set.count() for legacy, _ in permission_pairs)
