from django.contrib.auth.models import Group
from django.core.management.base import BaseCommand, CommandError

from cms.models import Page

from operations_portalcms_django.models import FocusAreaSection


FOCUS_PAGE_GROUP_MAP = {
    'CyberSecurity': 'Focus_Cybersecurity_Editors',
    'Data Transfer and Networking Support': 'Focus_Networking_dataTransfer_Editors',
    'Operational Support': 'Focus_operationsSupport_Editors',
    'Student Training and Engagement Program': 'Focus_STEP_Editors',
}

BLOCK_GROUP_NAME_MAP = {
    'CyberSecurity': {
        FocusAreaSection.SECTION_1: 'Focus_Cybersecurity_Section_1_Editors',
        FocusAreaSection.SECTION_2: 'Focus_Cybersecurity_Section_2_Editors',
        FocusAreaSection.SECTION_3: 'Focus_Cybersecurity_Section_3_Editors',
        FocusAreaSection.SECTION_4: 'Focus_Cybersecurity_Section_4_Editors',
        FocusAreaSection.SECTION_5: 'Focus_Cybersecurity_Section_5_Editors',
        FocusAreaSection.ADDITIONAL_LINKS: 'Focus_Cybersecurity_Additional_Links_Editors',
    },
    'Data Transfer and Networking Support': {
        FocusAreaSection.SECTION_1: 'Focus_Networking_dataTransfer_Section_1_Editors',
        FocusAreaSection.SECTION_2: 'Focus_Networking_dataTransfer_Section_2_Editors',
        FocusAreaSection.SECTION_3: 'Focus_Networking_dataTransfer_Section_3_Editors',
        FocusAreaSection.SECTION_4: 'Focus_Networking_dataTransfer_Section_4_Editors',
        FocusAreaSection.SECTION_5: 'Focus_Networking_dataTransfer_Section_5_Editors',
        FocusAreaSection.ADDITIONAL_LINKS: 'Focus_Networking_dataTransfer_Additional_Links_Editors',
    },
    'Operational Support': {
        FocusAreaSection.SECTION_1: 'Focus_operationsSupport_Section_1_Editors',
        FocusAreaSection.SECTION_2: 'Focus_operationsSupport_Section_2_Editors',
        FocusAreaSection.SECTION_3: 'Focus_operationsSupport_Section_3_Editors',
        FocusAreaSection.SECTION_4: 'Focus_operationsSupport_Section_4_Editors',
        FocusAreaSection.SECTION_5: 'Focus_operationsSupport_Section_5_Editors',
        FocusAreaSection.ADDITIONAL_LINKS: 'Focus_operationsSupport_Additional_Links_Editors',
    },
    'Student Training and Engagement Program': {
        FocusAreaSection.SECTION_1: 'Focus_STEP_Section_1_Editors',
        FocusAreaSection.SECTION_2: 'Focus_STEP_Section_2_Editors',
        FocusAreaSection.SECTION_3: 'Focus_STEP_Section_3_Editors',
        FocusAreaSection.SECTION_4: 'Focus_STEP_Section_4_Editors',
        FocusAreaSection.SECTION_5: 'Focus_STEP_Section_5_Editors',
        FocusAreaSection.ADDITIONAL_LINKS: 'Focus_STEP_Additional_Links_Editors',
    },
}


class Command(BaseCommand):
    help = 'Creates per-block focus-area editor groups and assigns page-level plus block-level owners to each managed section.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show planned block group and section ownership changes without saving them.',
        )
        parser.add_argument(
            '--replace-owner-groups',
            action='store_true',
            help='Replace each section owner group set instead of appending the required groups.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        replace_owner_groups = options['replace_owner_groups']

        self.stdout.write(self.style.SUCCESS('\n=== Configuring Focus Area Block Permissions ==='))

        total_groups_created = 0
        total_sections_created = 0
        total_sections_updated = 0

        for page_title, page_group_name in FOCUS_PAGE_GROUP_MAP.items():
            page = self._get_focus_page(page_title)
            page_group, group_created = Group.objects.get_or_create(name=page_group_name)
            if group_created:
                total_groups_created += 1
                self.stdout.write(f'+ Created page-level group {page_group_name}')

            self.stdout.write(f'\nPage: {page_title} (id={page.pk})')

            for section_key, block_group_name in BLOCK_GROUP_NAME_MAP[page_title].items():
                block_group, group_created = Group.objects.get_or_create(name=block_group_name)
                if group_created:
                    total_groups_created += 1
                    self.stdout.write(f'  + Created block group {block_group_name}')

                section, section_created = FocusAreaSection.objects.get_or_create(
                    page=page,
                    section_key=section_key,
                    defaults={'is_active': True},
                )
                if section_created:
                    total_sections_created += 1
                    self.stdout.write(f'  + Created section row for {section_key}')

                target_group_ids = {page_group.pk, block_group.pk}
                current_group_ids = set(section.owner_groups.values_list('pk', flat=True))

                if replace_owner_groups:
                    updated_group_ids = target_group_ids
                else:
                    updated_group_ids = current_group_ids | target_group_ids

                if current_group_ids != updated_group_ids:
                    total_sections_updated += 1
                    target_groups = Group.objects.filter(pk__in=updated_group_ids).order_by('name')
                    group_names = ', '.join(target_groups.values_list('name', flat=True))
                    self.stdout.write(f'  ↻ {section_key}: owner groups -> {group_names}')
                    if not dry_run:
                        section.owner_groups.set(target_groups)
                else:
                    owner_names = ', '.join(
                        section.owner_groups.order_by('name').values_list('name', flat=True)
                    )
                    self.stdout.write(f'  ✓ {section_key}: already configured ({owner_names})')

        summary = (
            f'\nSummary: {total_groups_created} group(s) created, '
            f'{total_sections_created} section row(s) created, '
            f'{total_sections_updated} section owner update(s)'
        )
        if dry_run:
            self.stdout.write(self.style.WARNING(summary + ' [dry run only]'))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def _get_focus_page(self, title):
        pages = Page.objects.all()
        matches = [page for page in pages if page.get_title('en', fallback=True) == title]

        if not matches:
            raise CommandError(f'Focus-area page not found: {title}')
        if len(matches) > 1:
            raise CommandError(f'Multiple focus-area pages found for title: {title}')
        return matches[0]
