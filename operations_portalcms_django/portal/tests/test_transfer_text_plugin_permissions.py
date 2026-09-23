from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management import call_command
from django.test import TestCase


class TransferTextPluginPermissionsTests(TestCase):
    def setUp(self):
        self.legacy_content_type = ContentType.objects.create(
            app_label="djangocms_text_ckeditor",
            model="text",
        )
        self.current_content_type = ContentType.objects.get(
            app_label="djangocms_text",
            model="text",
        )
        self.legacy_permissions = {}
        self.current_permissions = {}
        for action in ("add", "change", "delete", "view"):
            codename = f"{action}_text"
            self.legacy_permissions[codename] = Permission.objects.create(
                content_type=self.legacy_content_type,
                codename=codename,
                name=f"Can {action} legacy text",
            )
            self.current_permissions[codename] = Permission.objects.get(
                content_type=self.current_content_type,
                codename=codename,
            )

    def test_dry_run_reports_without_writing(self):
        group = Group.objects.create(name="legacy text editors")
        group.permissions.add(self.legacy_permissions["change_text"])
        output = StringIO()

        call_command(
            "transfer_text_plugin_permissions", "--dry-run", stdout=output
        )

        self.assertFalse(
            group.permissions.filter(
                pk=self.current_permissions["change_text"].pk
            ).exists()
        )
        self.assertIn("1 group grant(s)", output.getvalue())
        self.assertIn("DRY RUN", output.getvalue())

    def test_apply_copies_group_permissions_but_not_direct_user_permissions(self):
        group = Group.objects.create(name="legacy text editors")
        group.permissions.add(
            self.legacy_permissions["add_text"],
            self.legacy_permissions["change_text"],
        )
        user = get_user_model().objects.create_user(username="legacy-editor")
        user.user_permissions.add(self.legacy_permissions["delete_text"])

        output = StringIO()
        call_command("transfer_text_plugin_permissions", stdout=output)

        self.assertTrue(
            group.permissions.filter(
                pk=self.current_permissions["add_text"].pk
            ).exists()
        )
        self.assertTrue(
            group.permissions.filter(
                pk=self.current_permissions["change_text"].pk
            ).exists()
        )
        self.assertFalse(
            user.user_permissions.filter(
                pk=self.current_permissions["delete_text"].pk
            ).exists()
        )
        self.assertTrue(
            group.permissions.filter(
                pk=self.legacy_permissions["add_text"].pk
            ).exists()
        )
        self.assertIn(
            "1 legacy direct user grant(s) not transferred", output.getvalue()
        )
        self.assertIn("assign those users", output.getvalue())

    def test_apply_is_idempotent(self):
        group = Group.objects.create(name="legacy text editors")
        group.permissions.add(self.legacy_permissions["view_text"])

        call_command("transfer_text_plugin_permissions")
        call_command("transfer_text_plugin_permissions")

        self.assertEqual(
            group.permissions.filter(
                pk=self.current_permissions["view_text"].pk
            ).count(),
            1,
        )
