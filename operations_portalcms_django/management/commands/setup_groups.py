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

    def handle(self, *args, **options):
        # Create groups
        system_status_editors, created = Group.objects.get_or_create(name='System Status Editors')
        integration_editors, created = Group.objects.get_or_create(name='Integration News Editors')
        all_news_editors, created = Group.objects.get_or_create(name='All News Editors')
        
        # Get content types
        system_status_ct = ContentType.objects.get_for_model(SystemStatusNews)
        integration_ct = ContentType.objects.get_for_model(IntegrationNews)
        
        # Get permissions for SystemStatusNews
        system_status_permissions = Permission.objects.filter(content_type=system_status_ct)
        
        # Get permissions for IntegrationNews
        integration_permissions = Permission.objects.filter(content_type=integration_ct)
        
        # Assign permissions to System Status Editors group
        system_status_editors.permissions.set(system_status_permissions)
        self.stdout.write(self.style.SUCCESS(
            f'✓ System Status Editors group configured with {system_status_permissions.count()} permissions'
        ))
        
        # Assign permissions to Integration News Editors group
        integration_editors.permissions.set(integration_permissions)
        self.stdout.write(self.style.SUCCESS(
            f'✓ Integration News Editors group configured with {integration_permissions.count()} permissions'
        ))
        
        # Assign all news permissions to All News Editors group
        all_permissions = list(system_status_permissions) + list(integration_permissions)
        all_news_editors.permissions.set(all_permissions)
        self.stdout.write(self.style.SUCCESS(
            f'✓ All News Editors group configured with {len(all_permissions)} permissions'
        ))
        
        self.stdout.write(self.style.SUCCESS('\n=== Groups Created ==='))
        self.stdout.write(self.style.SUCCESS('1. System Status Editors - Can manage System Status News only'))
        self.stdout.write(self.style.SUCCESS('2. Integration News Editors - Can manage Integration News only'))
        self.stdout.write(self.style.SUCCESS('3. All News Editors - Can manage both types of news'))
        self.stdout.write(self.style.SUCCESS('\nTo assign users to groups, use Django Admin at /admin/auth/group/'))
