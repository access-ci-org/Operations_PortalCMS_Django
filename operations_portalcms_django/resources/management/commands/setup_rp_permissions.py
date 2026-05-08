"""
Management command to create Resource Provider permissions and groups

This creates Django permissions and groups based on CIDER RP groups that map to
CILogon group URNs from COmanage.

Run with: python manage.py setup_rp_permissions
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from resources.models import CiderGroups


class Command(BaseCommand):
    help = 'Creates Resource Provider permissions and groups mapped to CILogon URNs'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show permissions and groups that would be created or updated without writing changes.',
        )
        parser.add_argument(
            '--group-prefix',
            default='',
            help="Only process CIDER groups whose info_groupid starts with this prefix.",
        )
        parser.add_argument(
            '--group-type',
            action='append',
            default=[],
            help=(
                "Only process CIDER groups containing this group_types value. "
                "May be provided more than once."
            ),
        )
        parser.add_argument(
            '--skip-global-operations',
            action='store_true',
            help='Skip creating the global operations auth groups.',
        )

    def handle(self, *args, **options):
        content_type = ContentType.objects.get_for_model(CiderGroups)
        dry_run = bool(options['dry_run'])
        group_prefix = str(options['group_prefix'] or '')
        group_types = set(options['group_type'] or [])
        skip_global_operations = bool(options['skip_global_operations'])
        
        # Stats counters
        perms_created = 0
        perms_updated = 0
        groups_created = 0
        groups_updated = 0
        group_permissions_added = 0

        cider_groups = CiderGroups.objects.all().order_by('info_groupid')
        if group_prefix:
            cider_groups = cider_groups.filter(info_groupid__startswith=group_prefix)
        cider_groups = list(cider_groups)
        if group_types:
            cider_groups = [
                group
                for group in cider_groups
                if group_types.intersection(set(group.group_types or []))
            ]
        
        self.stdout.write('\n=== Creating Per-RP Permissions ===\n')
        if dry_run:
            self.stdout.write(self.style.WARNING('Dry run only; no database changes will be made.'))
        self.stdout.write(f'CIDER groups selected: {len(cider_groups)}')
        if group_prefix:
            self.stdout.write(f'  group-prefix: {group_prefix}')
        if group_types:
            self.stdout.write(f'  group-type filter: {", ".join(sorted(group_types))}')
        
        # Create permissions and groups for each RP (implementer, coordinator)
        for role in ["implementer", "coordinator"]:
            self.stdout.write(f'\nProcessing {role} role...')
            
            for rp_group in cider_groups:
                # Create permission codename: implementer_<groupid>
                codename = f"{role}_{rp_group.info_groupid}"
                perm_name = f"{role.capitalize()} for {rp_group.info_groupid}"

                permission = Permission.objects.filter(
                    content_type=content_type,
                    codename=codename,
                ).first()
                permission_exists = permission is not None

                if dry_run:
                    if permission_exists:
                        perms_updated += 1
                        self.stdout.write(f'  ↻ Would update permission: {codename}')
                    else:
                        perms_created += 1
                        self.stdout.write(f'  + Would create permission: {codename}')
                else:
                    # Create or update the permission
                    permission, created = Permission.objects.update_or_create(
                        content_type=content_type,
                        codename=codename,
                        defaults={
                            'name': perm_name,
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

                group = Group.objects.filter(name=group_name).first()
                group_exists = group is not None

                if dry_run:
                    if group_exists:
                        groups_updated += 1
                    else:
                        groups_created += 1
                        self.stdout.write(f'  + Would create group: {group_name}')

                    if not group_exists or not permission_exists or not group.permissions.filter(
                        content_type=content_type,
                        codename=codename,
                    ).exists():
                        group_permissions_added += 1
                        self.stdout.write(f'  + Would add {codename} to {group_name}')
                    continue

                # Create or update the permission
                group, created = Group.objects.get_or_create(name=group_name)
                
                if created:
                    groups_created += 1
                    self.stdout.write(f'  ✓ Created group: {group_name}')
                else:
                    groups_updated += 1
                
                # Add permission to group (if not already present)
                if not group.permissions.filter(codename=codename).exists():
                    group.permissions.add(permission)
                    group_permissions_added += 1
                    self.stdout.write(f'  ✓ Added {codename} to {group_name}')
        
        if skip_global_operations:
            self.stdout.write('\n\n=== Skipping Global Operations Permissions ===\n')
        else:
            self.stdout.write('\n\n=== Creating Global Operations Permissions ===\n')
        
        # Create global operations permissions
        global_roles = {
            "concierge": "Concierge",
            "badge.maintainer": "BadgeMaintainer",
            "roadmap.maintainer": "RoadmapMaintainer"
        }
        
        if not skip_global_operations:
            for codename, perm_name in global_roles.items():
                permission = Permission.objects.filter(
                    content_type=content_type,
                    codename=codename,
                ).first()
                permission_exists = permission is not None

                if dry_run:
                    if permission_exists:
                        perms_updated += 1
                        self.stdout.write(f'↻ Would update permission: {codename}')
                    else:
                        perms_created += 1
                        self.stdout.write(f'+ Would create permission: {codename}')
                else:
                    # Create or update permission
                    permission, created = Permission.objects.update_or_create(
                        content_type=content_type,
                        codename=codename,
                        defaults={
                            'name': perm_name,
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

                group = Group.objects.filter(name=group_name).first()
                group_exists = group is not None

                if dry_run:
                    if group_exists:
                        groups_updated += 1
                    else:
                        groups_created += 1
                        self.stdout.write(f'+ Would create group: {group_name}')

                    if not group_exists or not permission_exists or not group.permissions.filter(
                        content_type=content_type,
                        codename=codename,
                    ).exists():
                        group_permissions_added += 1
                        self.stdout.write(f'+ Would add {codename} to {group_name}')
                    continue

                group, created = Group.objects.get_or_create(name=group_name)

                if created:
                    groups_created += 1
                    self.stdout.write(f'✓ Created group: {group_name}')
                else:
                    groups_updated += 1

                # Add permission to group
                if not group.permissions.filter(codename=codename).exists():
                    group.permissions.add(permission)
                    group_permissions_added += 1
                    self.stdout.write(f'✓ Added {codename} to {group_name}')
        
        # Summary
        self.stdout.write('\n' + '='*60)
        status = 'Resource Provider Permissions Dry Run Complete' if dry_run else 'Resource Provider Permissions Setup Complete'
        self.stdout.write(self.style.SUCCESS(f'\n✓ {status}\n'))
        self.stdout.write('='*60)
        self.stdout.write(f'\nPermissions: {perms_created} created, {perms_updated} updated')
        self.stdout.write(f'Groups: {groups_created} created, {groups_updated} updated')
        self.stdout.write(f'Group permission links added: {group_permissions_added}')
        self.stdout.write('\n\nUsers authenticated via CILogon will automatically be assigned')
        self.stdout.write('to these groups if they belong to matching COmanage groups.')
        self.stdout.write('\n')
