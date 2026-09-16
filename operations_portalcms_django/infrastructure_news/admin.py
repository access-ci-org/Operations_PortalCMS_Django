from django.contrib import admin
from .models import SystemStatusNews


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
        if not change:
            obj.author = request.user
            can_publish = request.user.is_superuser or request.user.has_perm(
                'infrastructure_news.can_publish_systemstatusnews'
            )
            if not can_publish:
                obj.status = 'draft'
        super().save_model(request, obj, form, change)

    def save_related(self, request, form, formsets, change):
        super().save_related(request, form, formsets, change)
        obj = form.instance
        obj.affected_infrastructure = ', '.join(
            item.info_resourceid
            for item in obj.affected_infrastructure_items.order_by('resource_descriptive_name')
        )
        obj.save(update_fields=['affected_infrastructure'])

    @admin.display(description='Affected Infrastructure')
    def affected_infrastructure_display(self, obj):
        return obj.get_affected_infrastructure_display()

    def has_add_permission(self, request):
        if request.user.is_superuser:
            return True
        return request.user.has_perm('infrastructure_news.add_systemstatusnews')

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        return request.user.has_perm('infrastructure_news.change_systemstatusnews')

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if not request.user.has_perm('infrastructure_news.delete_systemstatusnews'):
            return False
        if obj is None:
            # Disable bulk delete for non-superusers: delete is author-only, so a
            # mixed selection would fail the whole batch with an opaque
            # PermissionDenied. Single-item delete gives clear per-item feedback.
            return False
        return obj.author == request.user
