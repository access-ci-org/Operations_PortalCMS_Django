"""
Management command to load test CIDER data for development/testing

This creates sample Resource Provider groups to test the permission system.
In production, this would sync from the actual CIDER API.

Run with: python manage.py load_test_cider_data
"""
from django.core.management.base import BaseCommand
from operations_portalcms_django.models import CiderGroups, CiderInfrastructure, CiderOrganizations


class Command(BaseCommand):
    help = 'Loads test CIDER data (Resource Provider groups, infrastructure, orgs)'

    def add_arguments(self, parser):
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Clear existing CIDER data before loading',
        )

    def handle(self, *args, **options):
        if options['clear']:
            self.stdout.write('Clearing existing CIDER data...')
            CiderGroups.objects.all().delete()
            CiderInfrastructure.objects.all().delete()
            CiderOrganizations.objects.all().delete()
            self.stdout.write(self.style.SUCCESS('✓ Cleared'))

        self.stdout.write('\n=== Loading Test CIDER Data ===\n')

        # Create test Resource Provider groups
        test_groups = [
            {
                'group_id': 1,
                'info_groupid': 'rp.access-ci.org',
                'group_descriptive_name': 'ACCESS Resource Providers',
                'group_description': 'Main ACCESS resource provider group',
                'group_types': ['resource_provider'],
            },
            {
                'group_id': 2,
                'info_groupid': 'rp.psc.edu',
                'group_descriptive_name': 'Pittsburgh Supercomputing Center',
                'group_description': 'PSC Resource Provider',
                'group_types': ['resource_provider', 'site'],
            },
            {
                'group_id': 3,
                'info_groupid': 'rp.tacc.utexas.edu',
                'group_descriptive_name': 'Texas Advanced Computing Center',
                'group_description': 'TACC Resource Provider',
                'group_types': ['resource_provider', 'site'],
            },
            {
                'group_id': 4,
                'info_groupid': 'rp.sdsc.edu',
                'group_descriptive_name': 'San Diego Supercomputer Center',
                'group_description': 'SDSC Resource Provider',
                'group_types': ['resource_provider', 'site'],
            },
            {
                'group_id': 5,
                'info_groupid': 'rp.ncsa.illinois.edu',
                'group_descriptive_name': 'National Center for Supercomputing Applications',
                'group_description': 'NCSA Resource Provider',
                'group_types': ['resource_provider', 'site'],
            },
        ]

        groups_created = 0
        for group_data in test_groups:
            group, created = CiderGroups.objects.update_or_create(
                group_id=group_data['group_id'],
                defaults=group_data
            )
            if created:
                groups_created += 1
                self.stdout.write(f'  ✓ Created: {group.info_groupid}')
            else:
                self.stdout.write(f'  ↻ Updated: {group.info_groupid}')

        # Create test organizations
        test_orgs = [
            {
                'organization_id': 1,
                'organization_name': 'Pittsburgh Supercomputing Center',
                'organization_abbrev': 'PSC',
                'organization_url': 'https://www.psc.edu',
            },
            {
                'organization_id': 2,
                'organization_name': 'Texas Advanced Computing Center',
                'organization_abbrev': 'TACC',
                'organization_url': 'https://www.tacc.utexas.edu',
            },
            {
                'organization_id': 3,
                'organization_name': 'San Diego Supercomputer Center',
                'organization_abbrev': 'SDSC',
                'organization_url': 'https://www.sdsc.edu',
            },
        ]

        orgs_created = 0
        for org_data in test_orgs:
            org, created = CiderOrganizations.objects.update_or_create(
                organization_id=org_data['organization_id'],
                defaults=org_data
            )
            if created:
                orgs_created += 1

        # Create test infrastructure
        test_infra = [
            {
                'cider_resource_id': 1,
                'cider_type': 'Compute',
                'info_resourceid': 'bridges2.psc.edu',
                'info_siteid': 'psc.edu',
                'resource_descriptive_name': 'Bridges-2',
                'resource_description': 'Converged HPC, AI, and Big Data infrastructure',
                'current_statuses': 'production',
                'latest_status': 'production',
                'provider_level': 'Level 1',
            },
            {
                'cider_resource_id': 2,
                'cider_type': 'Compute',
                'info_resourceid': 'stampede3.tacc.utexas.edu',
                'info_siteid': 'tacc.utexas.edu',
                'resource_descriptive_name': 'Stampede3',
                'resource_description': 'Dell supercomputer for large-scale computing',
                'current_statuses': 'production',
                'latest_status': 'production',
                'provider_level': 'Level 1',
            },
            {
                'cider_resource_id': 3,
                'cider_type': 'Storage',
                'info_resourceid': 'expanse-storage.sdsc.edu',
                'info_siteid': 'sdsc.edu',
                'resource_descriptive_name': 'Expanse Storage',
                'resource_description': 'High-performance storage system',
                'current_statuses': 'production',
                'latest_status': 'production',
                'provider_level': 'Level 2',
            },
        ]

        infra_created = 0
        for infra_data in test_infra:
            infra, created = CiderInfrastructure.objects.update_or_create(
                cider_resource_id=infra_data['cider_resource_id'],
                defaults=infra_data
            )
            if created:
                infra_created += 1

        # Summary
        self.stdout.write('\n' + '='*60)
        self.stdout.write(self.style.SUCCESS('\n✓ Test CIDER Data Loaded\n'))
        self.stdout.write('='*60)
        self.stdout.write(f'\nResource Provider Groups: {CiderGroups.objects.count()} total')
        self.stdout.write(f'Organizations: {CiderOrganizations.objects.count()} total')
        self.stdout.write(f'Infrastructure: {CiderInfrastructure.objects.count()} total')
        self.stdout.write('\nNext step: Run setup_rp_permissions to create Django groups\n')
