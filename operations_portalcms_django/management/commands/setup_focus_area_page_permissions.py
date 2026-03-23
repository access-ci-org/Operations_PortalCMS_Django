"""
Management command to configure Django CMS page permissions for focus-area pages.

This wires the existing focus editor groups to the four main focus-area pages:
- Focus_area_editors gets edit access on all four focus-area pages
- Each page-specific focus editor group gets edit access on its matching page

Run with:
    python manage.py setup_focus_area_page_permissions
    python manage.py setup_focus_area_page_permissions --dry-run
"""
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import Group
from cms.models import Page, PagePermission, ACCESS_PAGE_AND_DESCENDANTS


FOCUS_PAGE_GROUP_MAP = {
    'CyberSecurity': 'Focus_Cybersecurity_Editors',
    'Data Transfer and Networking Support': 'Focus_Networking_dataTransfer_Editors',
    'Operational Support': 'Focus_operationsSupport_Editors',
    'Student Training and Engagement Program': 'Focus_STEP_Editors',
}

GLOBAL_FOCUS_EDITORS_GROUP = 'Focus_area_editors'


class Command(BaseCommand):
    help = 'Configures Django CMS page permissions for the focus-area pages'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show the focus-area page permission changes without saving them.',
        )

    def handle(self, *args, **options):
        dry_run = options['dry_run']
        all_group_names = [GLOBAL_FOCUS_EDITORS_GROUP, *FOCUS_PAGE_GROUP_MAP.values()]

        groups = {}
        missing_groups = []
        for group_name in all_group_names:
            try:
                groups[group_name] = Group.objects.get(name=group_name)
            except Group.DoesNotExist:
                missing_groups.append(group_name)

        if missing_groups:
            raise CommandError(
                f"Missing required focus editor group(s): {', '.join(missing_groups)}"
            )

        self.stdout.write(self.style.SUCCESS('\n=== Configuring Focus Area Page Permissions ==='))
        self.stdout.write(
            'Using page-and-descendants scope so permissions apply to each focus page and its child pages.'
        )

        updated_count = 0
        created_count = 0

        for page_title, page_group_name in FOCUS_PAGE_GROUP_MAP.items():
            page = self._get_focus_page(page_title)
            target_groups = [
                groups[GLOBAL_FOCUS_EDITORS_GROUP],
                groups[page_group_name],
            ]

            self.stdout.write(
                f"\nPage: {page_title} (id={page.pk}, path={page.path})"
            )

            for group in target_groups:
                permission_defaults = {
                    'grant_on': ACCESS_PAGE_AND_DESCENDANTS,
                    'can_change': True,
                    'can_add': True,
                    'can_delete': False,
                    'can_publish': False,
                    'can_change_advanced_settings': False,
                    'can_change_permissions': False,
                    'can_move_page': True,
                    'can_view': False,
                }

                existing = PagePermission.objects.filter(page=page, group=group).first()
                if existing:
                    changed_fields = []
                    for field_name, expected_value in permission_defaults.items():
                        if getattr(existing, field_name) != expected_value:
                            changed_fields.append((field_name, getattr(existing, field_name), expected_value))

                    if changed_fields:
                        updated_count += 1
                        self.stdout.write(
                            f"  ↻ Update {group.name}: "
                            + ", ".join(
                                f"{field} {old!r}->{new!r}" for field, old, new in changed_fields
                            )
                        )
                        if not dry_run:
                            for field_name, _, expected_value in changed_fields:
                                setattr(existing, field_name, expected_value)
                            existing.save()
                    else:
                        self.stdout.write(f"  ✓ {group.name}: already configured")
                else:
                    created_count += 1
                    self.stdout.write(f"  + Create permission for {group.name}")
                    if not dry_run:
                        PagePermission.objects.create(
                            page=page,
                            group=group,
                            **permission_defaults,
                        )

        summary = f"\nSummary: {created_count} create(s), {updated_count} update(s)"
        if dry_run:
            self.stdout.write(self.style.WARNING(summary + ' [dry run only]'))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    def _get_focus_page(self, title):
        pages = Page.objects.all()
        matches = [page for page in pages if page.get_title('en', fallback=True) == title]

        if not matches:
            raise CommandError(f"Focus-area page not found: {title}")
        if len(matches) > 1:
            raise CommandError(f"Multiple focus-area pages found for title: {title}")
        return matches[0]
