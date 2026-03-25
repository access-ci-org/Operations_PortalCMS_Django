"""
Management command to configure Django CMS page permissions for focus-area pages.

This configures a page-level workflow for focus areas:
- Page-specific editors (Focus_STEP_Editors, etc.) can edit but NOT publish (must submit for review)
- Focus_area_editors (general group) can edit AND publish (acts as reviewer/publisher)

This enables the built-in Django CMS workflow:
1. STEP editor makes changes to STEP page
2. STEP editor saves as draft (automatic in CMS)
3. STEP editor requests publication via CMS "Publish Page" button (will show as pending)
4. Focus_area_editors member reviews draft and publishes

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
    help = 'Configures Django CMS page permissions for focus-area pages with workflow (edit vs publish separation)'

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
        self.stdout.write('Workflow: Page-specific editors can edit, general editors can publish')
        self.stdout.write(
            'Using page-and-descendants scope so permissions apply to each focus page and its child pages.'
        )

        updated_count = 0
        created_count = 0

        for page_title, page_group_name in FOCUS_PAGE_GROUP_MAP.items():
            page = self._get_focus_page(page_title)
            
            self.stdout.write(
                f"\nPage: {page_title} (id={page.pk}, path={page.path})"
            )

            # Global focus area editors - can review and publish
            global_group = groups[GLOBAL_FOCUS_EDITORS_GROUP]
            global_permission_defaults = {
                'grant_on': ACCESS_PAGE_AND_DESCENDANTS,
                'can_change': True,
                'can_add': True,
                'can_delete': False,
                'can_publish': True,  # Global editors CAN publish (reviewers)
                'can_change_advanced_settings': False,
                'can_change_permissions': False,
                'can_move_page': True,
                'can_view': True,  # Need view to access the page
            }
            
            result = self._configure_permission(page, global_group, global_permission_defaults, dry_run)
            if result == 'created':
                created_count += 1
            elif result == 'updated':
                updated_count += 1
            
            # Page-specific editors - can edit but NOT publish (must request review)
            page_group = groups[page_group_name]
            page_permission_defaults = {
                'grant_on': ACCESS_PAGE_AND_DESCENDANTS,
                'can_change': True,
                'can_add': True,
                'can_delete': False,
                'can_publish': False,  # Page-specific editors CANNOT publish
                'can_change_advanced_settings': False,
                'can_change_permissions': False,
                'can_move_page': True,
                'can_view': True,  # Need view to access the page
            }
            
            result = self._configure_permission(page, page_group, page_permission_defaults, dry_run)
            if result == 'created':
                created_count += 1
            elif result == 'updated':
                updated_count += 1

        summary = f"\nSummary: {created_count} create(s), {updated_count} update(s)"
        if dry_run:
            self.stdout.write(self.style.WARNING(summary + ' [dry run only]'))
        else:
            self.stdout.write(self.style.SUCCESS(summary))

    
    def _configure_permission(self, page, group, permission_defaults, dry_run):
        """Helper method to configure or update a page permission"""

    def _configure_permission(self, page, group, permission_defaults, dry_run):
        """Helper method to configure or update a page permission"""
        existing = PagePermission.objects.filter(page=page, group=group).first()
        if existing:
            changed_fields = []
            for field_name, expected_value in permission_defaults.items():
                if getattr(existing, field_name) != expected_value:
                    changed_fields.append((field_name, getattr(existing, field_name), expected_value))

            if changed_fields:
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
                return 'updated'
            else:
                self.stdout.write(f"  ✓ {group.name}: already configured")
                return 'unchanged'
        else:
            self.stdout.write(f"  + Create permission for {group.name}")
            if not dry_run:
                PagePermission.objects.create(
                    page=page,
                    group=group,
                    **permission_defaults,
                )
            return 'created'

    def _get_focus_page(self, title):
        pages = Page.objects.all()
        matches = [page for page in pages if page.get_title('en', fallback=True) == title]

        if not matches:
            raise CommandError(f"Focus-area page not found: {title}")
        if len(matches) > 1:
            raise CommandError(f"Multiple focus-area pages found for title: {title}")
        return matches[0]
