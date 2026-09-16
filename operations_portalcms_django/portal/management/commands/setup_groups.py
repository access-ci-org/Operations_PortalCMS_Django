"""
Management command to set up focus-area editor groups and permissions for
Operations Portal.

News permission groups (integration-news-publisher, infrastructure-news-publisher)
are not managed here: like other Portal Operations groups, they are created
manually and deliberately (Django admin or direct DB access) only when an actual
permission need exists - see dev_documentation/CURRENT_STATE.md.

Run with: python manage.py setup_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from cms.models import Page


class Command(BaseCommand):
    help = 'Creates focus-area editor groups and permissions for Operations Portal'

    def handle(self, *args, **options):
        version_ct = ContentType.objects.get(app_label='djangocms_versioning', model='version')
        unlock_version = Permission.objects.get(
            content_type=version_ct,
            codename='delete_versionlock',
        )

        # Configure Focus Area Editor Groups with CMS permissions
        self.stdout.write(self.style.SUCCESS('\n=== Configuring Focus Area Editor Groups ==='))
        page_ct = ContentType.objects.get_for_model(Page)
        change_page = Permission.objects.get(content_type=page_ct, codename='change_page')
        publish_page = Permission.objects.get(content_type=page_ct, codename='publish_page')
        view_page = Permission.objects.get(content_type=page_ct, codename='view_page')
        add_page = Permission.objects.get(content_type=page_ct, codename='add_page')
        use_structure = Permission.objects.get(content_type=ContentType.objects.get(app_label='cms', model='placeholder'), codename='use_structure')
        add_cmsplugin = Permission.objects.get(content_type=ContentType.objects.get(app_label='cms', model='cmsplugin'), codename='add_cmsplugin')
        change_cmsplugin = Permission.objects.get(content_type=ContentType.objects.get(app_label='cms', model='cmsplugin'), codename='change_cmsplugin')
        add_text = Permission.objects.get(content_type=ContentType.objects.get(app_label='djangocms_text_ckeditor', model='text'), codename='add_text')
        change_text = Permission.objects.get(content_type=ContentType.objects.get(app_label='djangocms_text_ckeditor', model='text'), codename='change_text')
        add_picture = Permission.objects.get(content_type=ContentType.objects.get(app_label='djangocms_picture', model='picture'), codename='add_picture')
        change_picture = Permission.objects.get(content_type=ContentType.objects.get(app_label='djangocms_picture', model='picture'), codename='change_picture')

        focus_editor_permissions = [
            view_page,
            add_page,
            change_page,
            use_structure,
            add_cmsplugin,
            change_cmsplugin,
            add_text,
            change_text,
            add_picture,
            change_picture,
        ]

        # General focus area editors - can change and publish
        focus_general, _ = Group.objects.get_or_create(name='Focus_area_editors')
        focus_general.permissions.add(*focus_editor_permissions, publish_page, unlock_version)
        self.stdout.write(self.style.SUCCESS(
            '✓ Focus_area_editors: can edit, publish, AND unlock draft locks (reviewer role)'
        ))

        # Page-specific focus area editors - can change but NOT publish
        specific_groups = [
            'Focus_Cybersecurity_Editors',
            'Focus_Networking_dataTransfer_Editors',
            'Focus_operationsSupport_Editors',
            'Focus_STEP_Editors',
        ]
        for group_name in specific_groups:
            group, _ = Group.objects.get_or_create(name=group_name)
            group.permissions.add(*focus_editor_permissions)
            # Explicitly remove publish_page if it exists
            group.permissions.remove(publish_page)
            self.stdout.write(self.style.SUCCESS(
                f'✓ {group_name}: can edit but NOT publish (must submit for review)'
            ))

        self.stdout.write(self.style.SUCCESS(
            '\nTo assign users to groups, use Django Admin at /admin/auth/group/'
        ))
        self.stdout.write(self.style.WARNING(
            '\nIMPORTANT: After configuring groups, run:'
        ))
        self.stdout.write(
            '  python manage.py setup_focus_area_page_permissions'
        )
        self.stdout.write(
            'This configures page-specific permissions for focus area workflow.'
        )
