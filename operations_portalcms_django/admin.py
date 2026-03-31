from django.contrib import admin
from django.contrib import messages
from django.db.models import Q
from cms.models import Page
from .models import (
    FocusAreaSection,
    SystemStatusNews, 
    IntegrationNews,
    CiderInfrastructure,
    CiderOrganizations,
    CiderFeatures,
    CiderGroups,
)
from .utils import (
    STEP_FOCUS_PAGE_TITLE,
    can_edit_focus_area_section,
    can_manage_news,
    is_rp_user,
)

GLOBAL_FOCUS_EDITORS_GROUP = 'Focus_area_editors'
FOCUS_PAGE_GROUP_MAP = {
    'Focus_Cybersecurity_Editors': 'CyberSecurity',
    'Focus_Networking_dataTransfer_Editors': 'Data Transfer and Networking Support',
    'Focus_STEP_Editors': 'Student Training and Engagement Program',
    'Focus_operationsSupport_Editors': 'Operational Support',
}


@admin.register(FocusAreaSection)
class FocusAreaSectionAdmin(admin.ModelAdmin):
    list_display = ['page_title', 'section_key', 'owner_group_list', 'is_active', 'updated_at', 'updated_by']
    list_filter = ['section_key', 'owner_groups', 'is_active']
    search_fields = ['heading', 'body', 'page__title_set__title', 'owner_groups__name']
    readonly_fields = ['updated_at', 'updated_by']
    autocomplete_fields = ['page', 'updated_by']
    filter_horizontal = ['owner_groups']

    fieldsets = (
        ('Section Identity', {
            'fields': ('page', 'section_key', 'owner_groups', 'is_active')
        }),
        ('Content', {
            'fields': ('heading', 'body')
        }),
        ('Metadata', {
            'fields': ('updated_at', 'updated_by'),
            'classes': ('collapse',)
        }),
    )

    @admin.display(description='Page')
    def page_title(self, obj):
        return obj.page.get_title('en', fallback=True)

    @admin.display(description='Owner Groups')
    def owner_group_list(self, obj):
        return ', '.join(obj.owner_groups.order_by('name').values_list('name', flat=True))

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if obj and obj.page.get_title('en', fallback=True) == STEP_FOCUS_PAGE_TITLE:
            return (
                ('Section Identity', {
                    'fields': ('page', 'section_key', 'is_active')
                }),
                ('Content', {
                    'fields': ('heading', 'body')
                }),
                ('Metadata', {
                    'fields': ('updated_at', 'updated_by'),
                    'classes': ('collapse',)
                }),
            )
        return fieldsets

    def _visible_page_ids_for_user(self, request):
        if request.user.is_superuser or request.user.groups.filter(name=GLOBAL_FOCUS_EDITORS_GROUP).exists():
            return None

        visible_titles = {
            page_title
            for group_name, page_title in FOCUS_PAGE_GROUP_MAP.items()
            if request.user.groups.filter(name=group_name).exists()
        }
        if not visible_titles:
            return set()

        return {
            page.pk
            for page in Page.objects.all()
            if page.get_title('en', fallback=True) in visible_titles
        }

    def get_queryset(self, request):
        qs = super().get_queryset(request).select_related('page', 'updated_by').prefetch_related('owner_groups')
        if request.user.is_superuser or request.user.groups.filter(name=GLOBAL_FOCUS_EDITORS_GROUP).exists():
            return qs

        visible_page_ids = self._visible_page_ids_for_user(request)
        owned_sections = Q(owner_groups__in=request.user.groups.all())
        if visible_page_ids is None:
            return qs
        if visible_page_ids:
            return qs.filter(Q(page_id__in=visible_page_ids) | owned_sections).distinct()
        return qs.filter(owned_sections).distinct()

    def save_model(self, request, obj, form, change):
        obj.updated_by = request.user
        super().save_model(request, obj, form, change)

    def has_module_permission(self, request):
        if request.user.is_superuser:
            return True
        return (
            request.user.groups.filter(
                name__in=[GLOBAL_FOCUS_EDITORS_GROUP, *FOCUS_PAGE_GROUP_MAP.keys()]
            ).exists()
            or FocusAreaSection.objects.filter(owner_groups__in=request.user.groups.all()).exists()
        )

    def has_view_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return self.has_module_permission(request)
        if can_edit_focus_area_section(request.user, obj):
            return True

        visible_page_ids = self._visible_page_ids_for_user(request)
        if visible_page_ids is None:
            return True
        return obj.page_id in visible_page_ids

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name=GLOBAL_FOCUS_EDITORS_GROUP).exists()

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj is None:
            return self.has_module_permission(request)
        return can_edit_focus_area_section(request.user, obj)

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.groups.filter(name=GLOBAL_FOCUS_EDITORS_GROUP).exists()


@admin.register(SystemStatusNews)
class SystemStatusNewsAdmin(admin.ModelAdmin):
    list_display = ['subject', 'infrastructure_news_type', 'start_datetime', 'affected_infrastructure_display', 'author', 'is_active']
    list_filter = ['is_active', 'infrastructure_news_type', 'start_datetime']
    search_fields = ['subject', 'content', 'affected_infrastructure']
    readonly_fields = ['created_at', 'updated_at', 'author']
    filter_horizontal = ['affected_infrastructure_items']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('subject', 'content', 'is_active')
        }),
        ('Infrastructure Details', {
            'fields': ('infrastructure_news_type', 'affected_infrastructure_items', 'start_datetime', 'end_datetime')
        }),
        ('Distribution Options', {
            'fields': ('send_email', 'email_list', 'post_to_slack', 'slack_channel'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('author', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.author = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        obj.affected_infrastructure = ", ".join(
            item.info_resourceid
            for item in obj.affected_infrastructure_items.order_by('resource_descriptive_name')
        )
        obj.save(update_fields=['affected_infrastructure'])

    @admin.display(description='Affected Infrastructure')
    def affected_infrastructure_display(self, obj):
        return obj.get_affected_infrastructure_display()
    
    def has_add_permission(self, request):
        """
        Allow adding news if user is:
        - Staff/superuser
        - In any RP group (coordinator or implementer)
        - In operations groups (concierge, maintainers)
        """
        if request.user.is_superuser:
            return True
        return can_manage_news(request.user)
    
    def has_change_permission(self, request, obj=None):
        """
        Allow editing if:
        - User is staff/superuser
        - User can manage news (RP or operations member)
        - User is the author
        """
        if request.user.is_superuser:
            return True
        
        # If editing specific object, check if they're the author
        if obj and obj.author == request.user:
            return True
        
        # Otherwise check if they can manage news
        return can_manage_news(request.user)
    
    def has_delete_permission(self, request, obj=None):
        """
        Allow deleting if:
        - User is staff/superuser
        - User is the author
        """
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Only allow deleting own news items
        if obj and obj.author == request.user:
            return True
        
        return False
    
    def get_queryset(self, request):
        """
        Show all news items to everyone who can access the admin.
        RP users can see all infrastructure news to stay informed.
        """
        qs = super().get_queryset(request)
        return qs
    
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        """
        Add help text for RP users about infrastructure field.
        """
        formfield = super().formfield_for_manytomany(db_field, request, **kwargs)
        
        if db_field.name == 'affected_infrastructure_items' and is_rp_user(request.user):
            if not request.user.is_staff:
                formfield.help_text = (
                    "Select one or more CIDER resources. "
                    "You can report on any infrastructure - cross-RP collaboration is encouraged."
                )
        
        return formfield


@admin.register(IntegrationNews)
class IntegrationNewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'affected_elements_display', 'author', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at', 'author']
    filter_horizontal = ['affected_elements']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'content', 'is_active')
        }),
        ('Integration Details', {
            'fields': ('news_type', 'affected_elements', 'effective_date', 'expiration_date')
        }),
        ('Metadata', {
            'fields': ('author', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        selected = list(obj.affected_elements.order_by('label'))
        obj.affected_element = selected[0].code if len(selected) == 1 else ''
        obj.save(update_fields=['affected_element'])

    @admin.display(description='Affected Elements')
    def affected_elements_display(self, obj):
        return obj.get_affected_elements_display()
    
    def has_add_permission(self, request):
        """Allow adding if user can manage news (RP or operations member)"""
        if request.user.is_superuser:
            return True
        return can_manage_news(request.user)
    
    def has_change_permission(self, request, obj=None):
        """Allow editing if user can manage news or is the author"""
        if request.user.is_superuser:
            return True
        
        if obj and obj.author == request.user:
            return True
        
        return can_manage_news(request.user)
    
    def has_delete_permission(self, request, obj=None):
        """Allow deleting if user is staff or the author"""
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        if obj and obj.author == request.user:
            return True
        
        return False
    
    def get_queryset(self, request):
        """Show all integration news to RP users"""
        qs = super().get_queryset(request)
        return qs


# ==================== CIDER Model Admins ====================

@admin.register(CiderInfrastructure)
class CiderInfrastructureAdmin(admin.ModelAdmin):
    list_display = ['info_resourceid', 'resource_descriptive_name', 'cider_type', 'latest_status', 'provider_level']
    list_filter = ['cider_type', 'latest_status', 'provider_level', 'project_affiliation']
    search_fields = ['info_resourceid', 'resource_descriptive_name', 'resource_description', 'info_siteid']
    readonly_fields = ['cider_resource_id', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('cider_resource_id', 'info_resourceid', 'info_siteid', 'cider_type',
                      'resource_descriptive_name', 'resource_description')
        }),
        ('Status', {
            'fields': ('current_statuses', 'latest_status', 'latest_status_begin', 
                      'latest_status_end', 'resource_status')
        }),
        ('Details', {
            'fields': ('recommended_use', 'access_description', 'parent_resource',
                      'project_affiliation', 'provider_level')
        }),
        ('Attributes', {
            'fields': ('protected_attributes', 'other_attributes'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )


@admin.register(CiderOrganizations)
class CiderOrganizationsAdmin(admin.ModelAdmin):
    list_display = ['organization_name', 'organization_abbrev', 'organization_id']
    search_fields = ['organization_name', 'organization_abbrev']
    readonly_fields = ['organization_id']
    
    fields = ('organization_id', 'organization_name', 'organization_abbrev', 
              'organization_url', 'other_attributes')


@admin.register(CiderFeatures)
class CiderFeaturesAdmin(admin.ModelAdmin):
    list_display = ['feature_category_name', 'feature_category_id']
    search_fields = ['feature_category_name', 'feature_category_description']
    readonly_fields = ['feature_category_id']
    
    fields = ('feature_category_id', 'feature_category_name', 'feature_category_description',
              'feature_category_types', 'features', 'other_attributes')


@admin.register(CiderGroups)
class CiderGroupsAdmin(admin.ModelAdmin):
    list_display = ['info_groupid', 'group_descriptive_name', 'group_id']
    search_fields = ['info_groupid', 'group_descriptive_name', 'group_description']
    readonly_fields = ['group_id']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('group_id', 'info_groupid', 'group_descriptive_name', 
                      'group_description', 'group_logo_url')
        }),
        ('Details', {
            'fields': ('group_types', 'info_resourceids', 'other_attributes'),
            'classes': ('collapse',)
        }),
    )
    
    # Show which Django groups are linked to this RP
    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if obj:
            return readonly + ['linked_django_groups']
        return readonly
    
    def linked_django_groups(self, obj):
        """Show which Django permission groups exist for this RP"""
        from django.contrib.auth.models import Group
        from django.utils.html import format_html
        
        groups = Group.objects.filter(
            name__contains=obj.info_groupid
        )
        
        if groups:
            group_list = '<br>'.join([
                f'• {g.name} ({g.permissions.count()} perms)'
                for g in groups
            ])
            return format_html(group_list)
        return format_html('<em>No Django groups created yet</em>')
    
    linked_django_groups.short_description = 'Linked Django Groups'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('group_id', 'info_groupid', 'group_descriptive_name', 
                      'group_description', 'group_logo_url')
        }),
        ('Permissions', {
            'fields': ('linked_django_groups',),
        }),
        ('Details', {
            'fields': ('group_types', 'info_resourceids', 'other_attributes'),
            'classes': ('collapse',)
        }),
    )
