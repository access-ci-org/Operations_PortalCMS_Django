from django.contrib import admin
from django.contrib import messages
from .models import (
    SystemStatusNews, 
    IntegrationNews,
    CiderInfrastructure,
    CiderOrganizations,
    CiderFeatures,
    CiderGroups,
)
from .utils import is_rp_user, can_manage_news


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
