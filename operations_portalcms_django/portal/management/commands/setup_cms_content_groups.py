"""Configure the site-wide CMS content editor and publisher groups."""

from django.conf import settings
from django.contrib.auth.models import Group, Permission
from django.contrib.sites.models import Site
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from cms.models import GlobalPagePermission
from cms.plugin_pool import plugin_pool


CONTENT_EDITOR_GROUP = (
    "urn:group:access-ci.org:operations.access-ci.org:content-editor"
)
CONTENT_PUBLISHER_GROUP = (
    "urn:group:access-ci.org:operations.access-ci.org:content-publisher"
)

# (application label, model name, permission codename)
BASE_EDITOR_PERMISSION_KEYS = (
    ("cms", "page", "change_page"),
    ("cms", "page", "view_page"),
    ("cms", "placeholder", "use_structure"),
    ("cms", "cmsplugin", "add_cmsplugin"),
    ("cms", "cmsplugin", "change_cmsplugin"),
    ("cms", "cmsplugin", "delete_cmsplugin"),
    ("cms", "cmsplugin", "view_cmsplugin"),
    (
        "djangocms_versioning",
        "pagecontentversion",
        "view_pagecontentversion",
    ),
)


def get_editor_permission_keys():
    """Return CMS core and model permissions for every user-facing plugin."""
    permission_keys = set(BASE_EDITOR_PERMISSION_KEYS)
    plugins = plugin_pool.get_all_plugins(root_plugin=False)
    for plugin in (plugin for plugin in plugins if not plugin.system):
        model_options = plugin.model._meta
        for action in ("add", "change", "delete", "view"):
            if action in model_options.default_permissions:
                permission_keys.add(
                    (
                        model_options.app_label,
                        model_options.model_name,
                        f"{action}_{model_options.model_name}",
                    )
                )
    return tuple(sorted(permission_keys))


PUBLISHER_EXTRA_PERMISSION_KEYS = (
    ("cms", "page", "publish_page"),
    (
        "djangocms_versioning",
        "pagecontentversion",
        "change_pagecontentversion",
    ),
    ("djangocms_versioning", "version", "delete_versionlock"),
)

GLOBAL_PERMISSION_FIELDS = (
    "can_change",
    "can_add",
    "can_delete",
    "can_publish",
    "can_change_advanced_settings",
    "can_change_permissions",
    "can_move_page",
    "can_view",
    "can_recover_page",
)


class Command(BaseCommand):
    help = "Configure least-privilege site-wide CMS editor and publisher groups."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Report the proposed changes without writing them.",
        )
        parser.add_argument(
            "--site-id",
            type=int,
            default=settings.SITE_ID,
            help="Django Site ID to authorize (defaults to settings.SITE_ID).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        site = self._get_site(options["site_id"])
        editor_permissions = self._resolve_permissions(get_editor_permission_keys())
        publisher_permissions = editor_permissions | self._resolve_permissions(
            PUBLISHER_EXTRA_PERMISSION_KEYS
        )

        specifications = (
            (
                CONTENT_EDITOR_GROUP,
                editor_permissions,
                self._global_defaults(can_publish=False),
            ),
            (
                CONTENT_PUBLISHER_GROUP,
                publisher_permissions,
                self._global_defaults(can_publish=True),
            ),
        )

        self.stdout.write(
            f"CMS content group configuration for Site {site.pk} ({site.domain})"
        )
        if dry_run:
            self.stdout.write(self.style.WARNING("DRY RUN: no database changes"))

        # Validate existing target rows before any write occurs.
        for group_name, _, _ in specifications:
            group = Group.objects.filter(name=group_name).first()
            if group is not None:
                self._get_group_global_permission(group)

        if dry_run:
            for specification in specifications:
                self._report_delta(*specification, site=site)
            return

        with transaction.atomic():
            for group_name, permissions, global_defaults in specifications:
                group, created = Group.objects.get_or_create(name=group_name)
                self.stdout.write(
                    f"{'Create' if created else 'Update'} group: {group_name}"
                )
                group.permissions.set(permissions)
                global_permission = self._get_group_global_permission(group)
                if global_permission is None:
                    global_permission = GlobalPagePermission.objects.create(
                        group=group,
                        user=None,
                        **global_defaults,
                    )
                else:
                    for field_name, expected_value in global_defaults.items():
                        setattr(global_permission, field_name, expected_value)
                    global_permission.save(update_fields=GLOBAL_PERMISSION_FIELDS)
                global_permission.sites.set([site])

        self.stdout.write(self.style.SUCCESS("CMS content groups configured."))

    def _get_site(self, site_id):
        try:
            return Site.objects.get(pk=site_id)
        except Site.DoesNotExist as exc:
            raise CommandError(f"Django Site does not exist: {site_id}") from exc

    def _resolve_permissions(self, permission_keys):
        resolved = set()
        missing = []
        for app_label, model, codename in permission_keys:
            try:
                permission = Permission.objects.get(
                    content_type__app_label=app_label,
                    content_type__model=model,
                    codename=codename,
                )
            except Permission.DoesNotExist:
                missing.append(f"{app_label}.{model}.{codename}")
            else:
                resolved.add(permission)
        if missing:
            raise CommandError(
                "Missing required permission(s): " + ", ".join(sorted(missing))
            )
        return resolved

    def _get_group_global_permission(self, group):
        rows = list(
            GlobalPagePermission.objects.filter(group=group).order_by("pk")
        )
        mixed_rows = [row.pk for row in rows if row.user_id is not None]
        group_rows = [row for row in rows if row.user_id is None]
        if mixed_rows:
            raise CommandError(
                f"Mixed user/group GlobalPagePermission rows for {group.name}: "
                + ", ".join(str(pk) for pk in mixed_rows)
            )
        if len(group_rows) > 1:
            raise CommandError(
                f"Duplicate GlobalPagePermission rows for {group.name}: "
                + ", ".join(str(row.pk) for row in group_rows)
            )
        return group_rows[0] if group_rows else None

    def _global_defaults(self, *, can_publish):
        defaults = {field_name: False for field_name in GLOBAL_PERMISSION_FIELDS}
        defaults["can_change"] = True
        defaults["can_publish"] = can_publish
        return defaults

    def _report_delta(self, group_name, permissions, global_defaults, *, site):
        group = Group.objects.filter(name=group_name).first()
        if group is None:
            self.stdout.write(f"Would create group: {group_name}")
            self.stdout.write(f"  Would assign {len(permissions)} permission(s)")
            for permission in sorted(permissions, key=self._permission_sort_key):
                self.stdout.write(f"    + {self._permission_label(permission)}")
            self.stdout.write(
                f"  Would create site-wide permission for Site {site.pk}"
            )
            return

        current_permissions = set(group.permissions.all())
        additions = sorted(
            permissions - current_permissions,
            key=lambda permission: (
                permission.content_type.app_label,
                permission.codename,
            ),
        )
        removals = sorted(
            current_permissions - permissions,
            key=lambda permission: (
                permission.content_type.app_label,
                permission.codename,
            ),
        )
        self.stdout.write(f"Would update group: {group_name}")
        self.stdout.write(f"  Permission additions: {len(additions)}")
        for permission in additions:
            self.stdout.write(f"    + {self._permission_label(permission)}")
        self.stdout.write(f"  Permission removals: {len(removals)}")
        for permission in removals:
            self.stdout.write(f"    - {self._permission_label(permission)}")

        global_permission = self._get_group_global_permission(group)
        if global_permission is None:
            self.stdout.write(
                f"  Would create site-wide permission for Site {site.pk}"
            )
            return

        changed_fields = [
            field_name
            for field_name, expected_value in global_defaults.items()
            if getattr(global_permission, field_name) != expected_value
        ]
        current_site_ids = set(global_permission.sites.values_list("pk", flat=True))
        if current_site_ids != {site.pk}:
            changed_fields.append("sites")
        if changed_fields:
            self.stdout.write(
                "  Global permission changes: " + ", ".join(changed_fields)
            )
        else:
            self.stdout.write("  Global permission already configured")

    @staticmethod
    def _permission_sort_key(permission):
        return (
            permission.content_type.app_label,
            permission.content_type.model,
            permission.codename,
        )

    @staticmethod
    def _permission_label(permission):
        return (
            f"{permission.content_type.app_label}."
            f"{permission.content_type.model}.{permission.codename}"
        )
