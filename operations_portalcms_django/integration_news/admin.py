from django.contrib import admin
from .models import IntegrationNews
from portal.utils import can_manage_news


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
        if request.user.is_superuser:
            return True
        return can_manage_news(request.user)

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if obj and obj.author == request.user:
            return True
        return can_manage_news(request.user)

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser or request.user.is_staff:
            return True
        if obj and obj.author == request.user:
            return True
        return False
