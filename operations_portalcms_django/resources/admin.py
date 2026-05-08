from django.contrib import admin
from .models import CiderInfrastructure, CiderOrganizations, CiderFeatures, CiderGroups


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
    fields = ('group_id', 'info_groupid', 'group_descriptive_name', 'group_description',
              'group_logo_url', 'group_types', 'info_resourceids', 'other_attributes')
