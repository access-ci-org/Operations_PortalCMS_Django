from django.contrib import admin
from .models import SystemStatusNews, IntegrationNews


@admin.register(SystemStatusNews)
class SystemStatusNewsAdmin(admin.ModelAdmin):
    list_display = ['subject', 'infrastructure_news_type', 'start_datetime', 'affected_infrastructure', 'author', 'is_active']
    list_filter = ['is_active', 'infrastructure_news_type', 'start_datetime']
    search_fields = ['subject', 'content', 'affected_infrastructure']
    readonly_fields = ['created_at', 'updated_at']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('subject', 'content', 'author', 'is_active')
        }),
        ('Infrastructure Details', {
            'fields': ('infrastructure_news_type', 'affected_infrastructure', 'start_datetime', 'end_datetime')
        }),
        ('Distribution Options', {
            'fields': ('send_email', 'email_list', 'post_to_slack', 'slack_channel'),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def save_model(self, request, obj, form, change):
        if not change:  # If creating new object
            obj.author = request.user
        super().save_model(request, obj, form, change)


@admin.register(IntegrationNews)
class IntegrationNewsAdmin(admin.ModelAdmin):
    list_display = ['title', 'author', 'created_at', 'is_active']
    list_filter = ['is_active', 'created_at']
    search_fields = ['title', 'content']
    readonly_fields = ['created_at', 'updated_at']
    
    def save_model(self, request, obj, form, change):
        if not change:
            obj.author = request.user
        super().save_model(request, obj, form, change)
