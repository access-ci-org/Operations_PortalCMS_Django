"""
Django CMS Plugins for News Feed Items
"""
from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cms.models.pluginmodel import CMSPlugin
from .models import SystemStatusNewsItemPlugin, IntegrationNewsItemPlugin


@plugin_pool.register_plugin
class SystemStatusNewsItemPluginPublisher(CMSPluginBase):
    """CMS Plugin for adding System Status News items"""
    model = SystemStatusNewsItemPlugin
    name = "System Status News Item"
    render_template = "operations_portalcms_django/plugins/system_status_news_item.html"
    cache = False
    
    fieldsets = [
        (None, {
            'fields': ('title', 'content', 'author')
        }),
    ]
    
    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        context['instance'] = instance
        return context


@plugin_pool.register_plugin
class IntegrationNewsItemPluginPublisher(CMSPluginBase):
    """CMS Plugin for adding Integration News items"""
    model = IntegrationNewsItemPlugin
    name = "Integration News Item"
    render_template = "operations_portalcms_django/plugins/integration_news_item.html"
    cache = False
    
    fieldsets = [
        (None, {
            'fields': ('title', 'content', 'author')
        }),
    ]
    
    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        context['instance'] = instance
        return context


@plugin_pool.register_plugin
class SystemStatusNewsFeedPlugin(CMSPluginBase):
    """CMS Plugin to display all System Status News items in chronological order"""
    model = CMSPlugin
    name = "System Status News Feed"
    render_template = "operations_portalcms_django/plugins/system_status_news_feed.html"
    cache = False
    allow_children = True
    child_classes = ['SystemStatusNewsItemPluginPublisher']
    
    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        # Get all child news items, ordered by date (newest first)
        children = instance.child_plugin_instances or []
        news_items = [child for child in children if isinstance(child, SystemStatusNewsItemPlugin)]
        news_items.sort(key=lambda x: x.published_date, reverse=True)
        context['news_items'] = news_items
        return context


@plugin_pool.register_plugin
class IntegrationNewsFeedPlugin(CMSPluginBase):
    """CMS Plugin to display all Integration News items in chronological order"""
    model = CMSPlugin
    name = "Integration News Feed"
    render_template = "operations_portalcms_django/plugins/integration_news_feed.html"
    cache = False
    allow_children = True
    child_classes = ['IntegrationNewsItemPluginPublisher']
    
    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        # Get all child news items, ordered by date (newest first)
        children = instance.child_plugin_instances or []
        news_items = [child for child in children if isinstance(child, IntegrationNewsItemPlugin)]
        news_items.sort(key=lambda x: x.published_date, reverse=True)
        context['news_items'] = news_items
        return context
