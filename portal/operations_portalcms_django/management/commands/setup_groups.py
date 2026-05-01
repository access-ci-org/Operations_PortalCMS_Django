"""
Management command to set up user groups and permissions for Operations Portal
Run with: python manage.py setup_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from operations_portalcms_django.models import SystemStatusNews, IntegrationNews
from cms.models import Page


class Command(BaseCommand):
    help = 'Creates user groups and assigns permissions for Operations Portal'

    def add_arguments(self, parser):
        parser.add_argument(
            '--migrate-legacy-memberships',
            action='store_true',
            help='Copy users from legacy editor groups into the new manager groups.',
        )
        parser.add_argument(
            '--delete-legacy-groups',
            action='store_true',
            help='Delete legacy editor groups after the new groups are configured.',
        )

    def handle(self, *args, **options):
        # Get content types
        system_status_ct = ContentType.objects.get_for_model(SystemStatusNews)
        integration_ct = ContentType.objects.get_for_model(IntegrationNews)
        version_ct = ContentType.objects.get(app_label='djangocms_versioning', model='version')
        unlock_version = Permission.objects.get(
            content_type=version_ct,
            codename='delete_versionlock',
        )

        def get_permissions(content_type, codenames):
            permissions = []
            for codename in codenames:
                permissions.append(
                    Permission.objects.get(content_type=content_type, codename=codename)
                )
            return permissions

        group_definitions = [
            (
                'System Status Authors',
                get_permissions(
                    system_status_ct,
                    ['view_systemstatusnews', 'add_systemstatusnews', 'change_systemstatusnews'],
                ),
                'Can create and edit System Status news; must submit for review to publish',
            ),
            (
                'System Status Managers',
                get_permissions(
                    system_status_ct,
                    [
                        'view_systemstatusnews',
                        'add_systemstatusnews',
                        'change_systemstatusnews',
                        'delete_systemstatusnews',
                        'can_review_systemstatusnews',
                        'can_publish_systemstatusnews',
                    ],
                ) + [unlock_version],
                'Can fully manage, review, and publish System Status news',
            ),
            (
                'Integration News Authors',
                get_permissions(
                    integration_ct,
                    ['view_integrationnews', 'add_integrationnews', 'change_integrationnews'],
                ),
                'Can create and edit Integration News; must submit for review to publish',
            ),
            (
                'Integration News Managers',
                get_permissions(
                    integration_ct,
                    [
                        'view_integrationnews',
                        'add_integrationnews',
                        'change_integrationnews',
                        'delete_integrationnews',
                        'can_review_integrationnews',
                        'can_publish_integrationnews',
                    ],
                ) + [unlock_version],
                'Can fully manage, review, and publish Integration News',
            ),
        ]

        self.stdout.write(self.style.SUCCESS('\n=== Configuring News Groups ==='))
        configured_groups = {}
        for group_name, permissions, description in group_definitions:
            group, _ = Group.objects.get_or_create(name=group_name)
            group.permissions.set(permissions)
            configured_groups[group_name] = group
            self.stdout.write(self.style.SUCCESS(
                f'✓ {group_name} configured with {len(permissions)} permissions'
            ))
            self.stdout.write(f'  {description}')
        
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

        legacy_group_targets = {
            'System Status Editors': ['System Status Managers'],
            'System Status Publishers': ['System Status Managers'],
            'Integration News Editors': ['Integration News Managers'],
            'Integration News Publishers': ['Integration News Managers'],
            'All News Editors': ['System Status Managers', 'Integration News Managers'],
        }

        if options['migrate_legacy_memberships']:
            self.stdout.write(self.style.SUCCESS('\n=== Migrating Legacy Group Memberships ==='))
            for legacy_name, target_names in legacy_group_targets.items():
                try:
                    legacy_group = Group.objects.get(name=legacy_name)
                except Group.DoesNotExist:
                    self.stdout.write(f'- {legacy_name}: not found, skipping')
                    continue

                users = list(legacy_group.user_set.all())
                for user in users:
                    for target_name in target_names:
                        user.groups.add(configured_groups[target_name])
                self.stdout.write(self.style.SUCCESS(
                    f'✓ {legacy_name}: migrated {len(users)} user(s) to {", ".join(target_names)}'
                ))

        if options['delete_legacy_groups']:
            self.stdout.write(self.style.WARNING('\n=== Deleting Legacy Editor Groups ==='))
            for legacy_name in legacy_group_targets:
                deleted_count, _ = Group.objects.filter(name=legacy_name).delete()
                if deleted_count:
                    self.stdout.write(self.style.SUCCESS(f'✓ Deleted {legacy_name}'))
                else:
                    self.stdout.write(f'- {legacy_name}: not found, skipping')
        else:
            self.stdout.write(self.style.WARNING(
                '\nLegacy editor groups are not modified or deleted by this command.'
            ))
            self.stdout.write(
                'Use --migrate-legacy-memberships to copy users into the new manager groups.'
            )
            self.stdout.write(
                'Use --delete-legacy-groups to remove the legacy groups after testing.'
            )

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
