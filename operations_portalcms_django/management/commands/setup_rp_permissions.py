"""
Management command to create Resource Provider permissions and groups

This creates Django permissions and groups based on CIDER RP groups that map to
CILogon group URNs from COmanage.

Run with: python manage.py setup_rp_permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from operations_portalcms_django.models import CiderGroups


class Command(BaseCommand):
    help = 'Creates Resource Provider permissions and groups mapped to CILogon URNs'

    def handle(self, *args, **options):
        content_type = ContentType.objects.get_for_model(CiderGroups)
        
        # Stats counters
        perms_created = 0
        perms_updated = 0
        groups_created = 0
        groups_updated = 0
        
        self.stdout.write('\n=== Creating Per-RP Permissions ===\n')
        
        # Create permissions and groups for each RP (implementer, coordinator)
        for role in ["implementer", "coordinator"]:
            self.stdout.write(f'\nProcessing {role} role...')
            
            for rp_group in CiderGroups.objects.all():
                # Create permission codename: implementer_<groupid>
                codename = f"{role}_{rp_group.info_groupid}"
                perm_name = f"{role.capitalize()} for {rp_group.info_groupid}"
                
                # Create or update the permission
                permission, created = Permission.objects.update_or_create(
                    codename=codename,
                    defaults={
                        'name': perm_name,
                        'content_type': content_type
                    }
                )
                
                if created:
                    perms_created += 1
                    self.stdout.write(f'  ✓ Created permission: {codename}')
                else:
                    perms_updated += 1
                    self.stdout.write(f'  ↻ Updated permission: {codename}')
                
                # Create Django group matching CILogon URN format
                # Format: urn:group:access-ci.org:<groupid>:<role>
                group_name = f"urn:group:access-ci.org:{rp_group.info_groupid}:{role}"
                
                group, created = Group.objects.get_or_create(name=group_name)
                
                if created:
                    groups_created += 1
                    self.stdout.write(f'  ✓ Created group: {group_name}')
                else:
                    groups_updated += 1
                
                # Add permission to group (if not already present)
                if not group.permissions.filter(codename=codename).exists():
                    group.permissions.add(permission)
                    self.stdout.write(f'  ✓ Added {codename} to {group_name}')
        
        self.stdout.write('\n\n=== Creating Global Operations Permissions ===\n')
        
        # Create global operations permissions
        global_roles = {
            "concierge": "Concierge",
            "badge.maintainer": "BadgeMaintainer",
            "roadmap.maintainer": "RoadmapMaintainer"
        }
        
        for codename, perm_name in global_roles.items():
            # Create or update permission
            permission, created = Permission.objects.update_or_create(
                codename=codename,
                defaults={
                    'name': perm_name,
                    'content_type': content_type
                }
            )
            
            if created:
                perms_created += 1
                self.stdout.write(f'✓ Created permission: {codename}')
            else:
                perms_updated += 1
                self.stdout.write(f'↻ Updated permission: {codename}')
            
            # Create Django group matching CILogon URN format
            # Format: urn:group:access-ci.org:operations.access-ci.org:<role>
            group_name = f"urn:group:access-ci.org:operations.access-ci.org:{codename}"
            
            group, created = Group.objects.get_or_create(name=group_name)
            
            if created:
                groups_created += 1
                self.stdout.write(f'✓ Created group: {group_name}')
            else:
                groups_updated += 1
            
            # Add permission to group
            if not group.permissions.filter(codename=codename).exists():
                group.permissions.add(permission)
                self.stdout.write(f'✓ Added {codename} to {group_name}')
        
        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('\n✓ Resource Provider Permissions Setup Complete\n'))
        self.stdout.write('='*60)
        self.stdout.write(f'\nPermissions: {perms_created} created, {perms_updated} updated')
        self.stdout.write(f'Groups: {groups_created} created, {groups_updated} updated')
        self.stdout.write('\n\nUsers authenticated via CILogon will automatically be assigned')
        self.stdout.write('to these groups if they belong to matching COmanage groups.')
        self.stdout.write('\n')
