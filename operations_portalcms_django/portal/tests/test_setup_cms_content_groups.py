from io import StringIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.contrib.sites.models import Site
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from cms.api import create_page
from cms.models import GlobalPagePermission
from cms.utils.page_permissions import (
    user_can_add_page,
    user_can_change_page,
    user_can_change_page_advanced_settings,
    user_can_change_page_permissions,
    user_can_delete_page,
    user_can_move_page,
    user_can_publish_page,
)
from djangocms_versioning.models import Version

from portal.management.commands.setup_cms_content_groups import (
    CONTENT_EDITOR_GROUP,
    CONTENT_PUBLISHER_GROUP,
    GLOBAL_PERMISSION_FIELDS,
    PUBLISHER_EXTRA_PERMISSION_KEYS,
    get_editor_permission_keys,
)


class SetupCMSContentGroupsTests(TestCase):
    def setUp(self):
        self.site, _ = Site.objects.update_or_create(
            pk=1,
            defaults={"domain": "example.test", "name": "Test Site"},
        )

    def _permission_names(self, group):
        return {
            (
                permission.content_type.app_label,
                permission.content_type.model,
                permission.codename,
            )
            for permission in group.permissions.select_related("content_type")
        }

    def _global_permission(self, group):
        return GlobalPagePermission.objects.get(group=group, user__isnull=True)

    def test_dry_run_creates_nothing(self):
        output = StringIO()

        call_command("setup_cms_content_groups", "--dry-run", stdout=output)

        self.assertFalse(Group.objects.filter(name=CONTENT_EDITOR_GROUP).exists())
        self.assertFalse(Group.objects.filter(name=CONTENT_PUBLISHER_GROUP).exists())
        self.assertEqual(GlobalPagePermission.objects.count(), 0)
        self.assertIn("DRY RUN", output.getvalue())

    def test_apply_sets_exact_permissions_and_preserves_memberships(self):
        User = get_user_model()
        editor_user = User.objects.create_user(username="editor", password="unused")
        publisher_user = User.objects.create_user(
            username="publisher", password="unused"
        )
        editor_group = Group.objects.create(name=CONTENT_EDITOR_GROUP)
        publisher_group = Group.objects.create(name=CONTENT_PUBLISHER_GROUP)
        editor_user.groups.add(editor_group)
        publisher_user.groups.add(publisher_group)
        extra_permission = Permission.objects.get(
            content_type__app_label="cms",
            content_type__model="page",
            codename="delete_page",
        )
        editor_group.permissions.add(extra_permission)
        publisher_group.permissions.add(extra_permission)

        call_command("setup_cms_content_groups")

        editor_group.refresh_from_db()
        publisher_group.refresh_from_db()
        self.assertEqual(
            self._permission_names(editor_group), set(get_editor_permission_keys())
        )
        self.assertEqual(
            self._permission_names(publisher_group),
            set(get_editor_permission_keys())
            | set(PUBLISHER_EXTRA_PERMISSION_KEYS),
        )
        self.assertEqual(
            set(editor_user.groups.values_list("name", flat=True)),
            {CONTENT_EDITOR_GROUP},
        )
        self.assertEqual(
            set(publisher_user.groups.values_list("name", flat=True)),
            {CONTENT_PUBLISHER_GROUP},
        )

        editor_global = self._global_permission(editor_group)
        publisher_global = self._global_permission(publisher_group)
        for field_name in GLOBAL_PERMISSION_FIELDS:
            self.assertEqual(
                getattr(editor_global, field_name), field_name == "can_change"
            )
            self.assertEqual(
                getattr(publisher_global, field_name),
                field_name in {"can_change", "can_publish"},
            )
        self.assertEqual(
            set(editor_global.sites.values_list("pk", flat=True)), {self.site.pk}
        )
        self.assertEqual(
            set(publisher_global.sites.values_list("pk", flat=True)), {self.site.pk}
        )

    def test_effective_page_permissions_separate_editor_and_publisher(self):
        User = get_user_model()
        editor = User.objects.create_user(
            username="editor", password="unused", is_staff=True
        )
        publisher = User.objects.create_user(
            username="publisher", password="unused", is_staff=True
        )
        page = create_page(
            title="Permission Test",
            template="page.html",
            language="en",
            site=self.site,
            created_by=publisher,
        )

        call_command("setup_cms_content_groups")
        editor.groups.add(Group.objects.get(name=CONTENT_EDITOR_GROUP))
        publisher.groups.add(Group.objects.get(name=CONTENT_PUBLISHER_GROUP))

        self.assertTrue(user_can_change_page(editor, page, site=self.site))
        self.assertFalse(user_can_publish_page(editor, page, site=self.site))
        self.assertTrue(user_can_change_page(publisher, page, site=self.site))
        self.assertTrue(user_can_publish_page(publisher, page, site=self.site))
        self.assertTrue(
            editor.has_perms(
                [
                    "djangocms_file.change_folder",
                    "infrastructure_news.change_systemstatusnewsitemplugin",
                    "integration_news.change_integrationnewsitemplugin",
                ]
            )
        )
        self.assertTrue(
            publisher.has_perms(
                [
                    "djangocms_file.change_folder",
                    "infrastructure_news.change_systemstatusnewsitemplugin",
                    "integration_news.change_integrationnewsitemplugin",
                ]
            )
        )

        version = Version.objects.get()
        self.assertFalse(version.check_publish.as_bool(editor))
        self.assertTrue(version.check_publish.as_bool(publisher))
        self.assertTrue(
            editor.has_perm(
                "djangocms_versioning.view_pagecontentversion"
            )
        )
        self.assertFalse(
            editor.has_perm(
                "djangocms_versioning.change_pagecontentversion"
            )
        )
        self.assertTrue(
            publisher.has_perm(
                "djangocms_versioning.change_pagecontentversion"
            )
        )

        for user in (editor, publisher):
            self.assertFalse(user_can_add_page(user, site=self.site))
            self.assertFalse(user_can_delete_page(user, page, site=self.site))
            self.assertFalse(user_can_move_page(user, page, site=self.site))
            self.assertFalse(
                user_can_change_page_advanced_settings(user, page, site=self.site)
            )
            self.assertFalse(
                user_can_change_page_permissions(user, page, site=self.site)
            )

    def test_registered_plugin_models_are_included(self):
        permission_keys = set(get_editor_permission_keys())

        self.assertIn(
            ("djangocms_file", "folder", "change_folder"), permission_keys
        )
        self.assertIn(
            (
                "infrastructure_news",
                "systemstatusnewsitemplugin",
                "change_systemstatusnewsitemplugin",
            ),
            permission_keys,
        )
        self.assertIn(
            (
                "integration_news",
                "integrationnewsitemplugin",
                "change_integrationnewsitemplugin",
            ),
            permission_keys,
        )

    def test_apply_is_idempotent(self):
        call_command("setup_cms_content_groups")
        first_group_ids = list(
            Group.objects.filter(
                name__in=[CONTENT_EDITOR_GROUP, CONTENT_PUBLISHER_GROUP]
            )
            .order_by("name")
            .values_list("pk", flat=True)
        )
        first_global_ids = list(
            GlobalPagePermission.objects.filter(
                group__name__in=[CONTENT_EDITOR_GROUP, CONTENT_PUBLISHER_GROUP]
            )
            .order_by("group__name")
            .values_list("pk", flat=True)
        )

        call_command("setup_cms_content_groups")

        self.assertEqual(
            list(
                Group.objects.filter(
                    name__in=[CONTENT_EDITOR_GROUP, CONTENT_PUBLISHER_GROUP]
                )
                .order_by("name")
                .values_list("pk", flat=True)
            ),
            first_group_ids,
        )
        self.assertEqual(
            list(
                GlobalPagePermission.objects.filter(
                    group__name__in=[CONTENT_EDITOR_GROUP, CONTENT_PUBLISHER_GROUP]
                )
                .order_by("group__name")
                .values_list("pk", flat=True)
            ),
            first_global_ids,
        )

    def test_missing_site_fails_without_writes(self):
        with self.assertRaises(CommandError):
            call_command("setup_cms_content_groups", "--site-id", "999")

        self.assertFalse(Group.objects.filter(name=CONTENT_EDITOR_GROUP).exists())
        self.assertFalse(Group.objects.filter(name=CONTENT_PUBLISHER_GROUP).exists())

    def test_missing_permission_fails_without_writes(self):
        Permission.objects.filter(
            content_type__app_label="cms",
            content_type__model="page",
            codename="change_page",
        ).delete()

        with self.assertRaises(CommandError):
            call_command("setup_cms_content_groups")

        self.assertFalse(Group.objects.filter(name=CONTENT_EDITOR_GROUP).exists())
        self.assertFalse(Group.objects.filter(name=CONTENT_PUBLISHER_GROUP).exists())

    def test_dry_run_does_not_modify_existing_groups(self):
        editor_group = Group.objects.create(name=CONTENT_EDITOR_GROUP)
        extra_permission = Permission.objects.get(
            content_type__app_label="cms",
            content_type__model="page",
            codename="delete_page",
        )
        editor_group.permissions.add(extra_permission)

        output = StringIO()
        call_command("setup_cms_content_groups", "--dry-run", stdout=output)

        self.assertEqual(set(editor_group.permissions.all()), {extra_permission})
        self.assertFalse(Group.objects.filter(name=CONTENT_PUBLISHER_GROUP).exists())
        self.assertEqual(GlobalPagePermission.objects.count(), 0)
        self.assertIn("- cms.page.delete_page", output.getvalue())
        self.assertIn(
            "+ integration_news.integrationnewsitemplugin."
            "change_integrationnewsitemplugin",
            output.getvalue(),
        )

    def test_duplicate_global_permissions_fail_before_other_group_changes(self):
        editor_group = Group.objects.create(name=CONTENT_EDITOR_GROUP)
        publisher_group = Group.objects.create(name=CONTENT_PUBLISHER_GROUP)
        extra_permission = Permission.objects.get(
            content_type__app_label="cms",
            content_type__model="page",
            codename="delete_page",
        )
        editor_group.permissions.add(extra_permission)
        for _ in range(2):
            global_permission = GlobalPagePermission.objects.create(
                group=publisher_group,
                can_change=True,
            )
            global_permission.sites.add(self.site)

        with self.assertRaises(CommandError):
            call_command("setup_cms_content_groups")

        self.assertEqual(set(editor_group.permissions.all()), {extra_permission})
        self.assertEqual(
            GlobalPagePermission.objects.filter(group=publisher_group).count(), 2
        )

    def test_mixed_user_group_global_permission_fails_closed(self):
        User = get_user_model()
        user = User.objects.create_user(username="mixed", password="unused")
        editor_group = Group.objects.create(name=CONTENT_EDITOR_GROUP)
        mixed_permission = GlobalPagePermission.objects.create(
            user=user,
            group=editor_group,
            can_change=True,
        )
        mixed_permission.sites.add(self.site)

        with self.assertRaises(CommandError):
            call_command("setup_cms_content_groups")

        self.assertFalse(Group.objects.filter(name=CONTENT_PUBLISHER_GROUP).exists())
        self.assertEqual(editor_group.permissions.count(), 0)
