"""
Management command to sync CIDER data from Operations API

This fetches Resource Provider groups and organizations from the CIDER API
and syncs them to the local database.

Run with: python manage.py sync_cider_from_api
"""
import requests
from django.core.management.base import BaseCommand
from operations_portalcms_django.models import CiderGroups, CiderOrganizations


class Command(BaseCommand):
    help = 'Syncs CIDER data from Operations API (groups, organizations)'
    
    API_BASE = "https://operations-api.access-ci.org/wh2/cider"

    def add_arguments(self, parser):
        parser.add_argument(
            '--api-url',
            type=str,
            default=None,
            help='Override API base URL (default: https://operations-api.access-ci.org/wh2/cider)',
        )

    def handle(self, *args, **options):
        if options['api_url']:
            self.API_BASE = options['api_url']
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write('SYNCING CIDER DATA FROM API')
        self.stdout.write('='*70 + '\n')
        
        # Sync groups (Resource Providers)
        self.sync_groups()
        
        # Sync organizations
        self.sync_organizations()
        
        self.stdout.write('\n' + '='*70)
        self.stdout.write(self.style.SUCCESS('✓ CIDER Data Sync Complete'))
        self.stdout.write('='*70 + '\n')
    
    def sync_groups(self):
        """Sync Resource Provider groups from CIDER API"""
        self.stdout.write('\n--- Syncing Resource Provider Groups ---\n')
        
        url = f"{self.API_BASE}/v2/access-active-groups/"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to fetch groups: {e}'))
            return
        
        active_groups = data.get("results", {}).get("active_groups", [])
        
        groups_created = 0
        groups_updated = 0
        
        for group in active_groups:
            # Only sync Resource Provider groups (rp.*)
            info_groupid = group.get("info_groupid", "")
            if not info_groupid.startswith("rp."):
                continue
            
            group_id = group.get("group_id")
            
            obj, created = CiderGroups.objects.update_or_create(
                group_id=group_id,
                defaults={
                    "info_groupid": info_groupid,
                    "group_descriptive_name": group.get("group_descriptive_name", ""),
                    "group_description": group.get("group_description"),
                    "group_logo_url": group.get("group_logo_url"),
                    "group_types": group.get("group_types", []),
                    "info_resourceids": group.get("rollup_info_resourceids", []),
                    "other_attributes": {
                        "rollup_feature_ids": group.get("rollup_feature_ids", []),
                        "rollup_organization_ids": group.get("rollup_organization_ids", []),
                        "rollup_badge_ids": group.get("rollup_badge_ids", []),
                    }
                }
            )
            
            if created:
                groups_created += 1
                self.stdout.write(f'  ✓ Created: {info_groupid}')
            else:
                groups_updated += 1
                self.stdout.write(f'  ↻ Updated: {info_groupid}')
        
        self.stdout.write(f'\nGroups: {groups_created} created, {groups_updated} updated')
    
    def sync_organizations(self):
        """Sync organizations from CIDER API"""
        self.stdout.write('\n--- Syncing Organizations ---\n')
        
        url = f"{self.API_BASE}/v1/organizations/"
        
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            self.stdout.write(self.style.ERROR(f'✗ Failed to fetch organizations: {e}'))
            return
        
        organizations = data.get("results", [])
        
        orgs_created = 0
        orgs_updated = 0
        
        for org in organizations:
            organization_id = org.get("organization_id")
            
            obj, created = CiderOrganizations.objects.update_or_create(
                organization_id=organization_id,
                defaults={
                    "organization_name": org.get("organization_name", ""),
                    "organization_abbrev": org.get("organization_abbrev", ""),
                    "organization_url": org.get("organization_url"),
                    "other_attributes": org.get("other_attributes", {}),
                }
            )
            
            if created:
                orgs_created += 1
                self.stdout.write(f'  ✓ Created: {org.get("organization_abbrev")}')
            else:
                orgs_updated += 1
        
        self.stdout.write(f'\nOrganizations: {orgs_created} created, {orgs_updated} updated')
