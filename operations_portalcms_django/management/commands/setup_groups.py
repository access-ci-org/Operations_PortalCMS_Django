"""
Management command to set up user groups and permissions for Operations Portal
Run with: python manage.py setup_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from operations_portalcms_django.models import SystemStatusNews, IntegrationNews


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
                'Can create and edit System Status news',
            ),
            (
                'System Status Publishers',
                get_permissions(
                    system_status_ct,
                    [
                        'view_systemstatusnews',
                        'add_systemstatusnews',
                        'change_systemstatusnews',
                        'can_publish_systemstatusnews',
                    ],
                ),
                'Can create, edit, and publish System Status news',
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
                ),
                'Can fully manage and review System Status news',
            ),
            (
                'Integration News Authors',
                get_permissions(
                    integration_ct,
                    ['view_integrationnews', 'add_integrationnews', 'change_integrationnews'],
                ),
                'Can create and edit Integration News',
            ),
            (
                'Integration News Publishers',
                get_permissions(
                    integration_ct,
                    [
                        'view_integrationnews',
                        'add_integrationnews',
                        'change_integrationnews',
                        'can_publish_integrationnews',
                    ],
                ),
                'Can create, edit, and publish Integration News',
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
                ),
                'Can fully manage and review Integration News',
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

        legacy_group_targets = {
            'System Status Editors': ['System Status Managers'],
            'Integration News Editors': ['Integration News Managers'],
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
