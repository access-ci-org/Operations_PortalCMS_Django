from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cms.models.pluginmodel import CMSPlugin
from .models import SystemStatusNewsItemPlugin


@plugin_pool.register_plugin
class SystemStatusNewsItemPluginPublisher(CMSPluginBase):
    model = SystemStatusNewsItemPlugin
    name = "System Status News Item"
    render_template = "portal/plugins/system_status_news_item.html"
    cache = False
    fieldsets = [(None, {'fields': ('title', 'content', 'author')})]

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        context['instance'] = instance
        return context


@plugin_pool.register_plugin
class SystemStatusNewsFeedPlugin(CMSPluginBase):
    model = CMSPlugin
    name = "System Status News Feed"
    render_template = "portal/plugins/system_status_news_feed.html"
    cache = False
    allow_children = True
    child_classes = ['SystemStatusNewsItemPluginPublisher']

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        children = instance.child_plugin_instances or []
        news_items = [c for c in children if isinstance(c, SystemStatusNewsItemPlugin)]
        news_items.sort(key=lambda x: x.published_date, reverse=True)
        context['news_items'] = news_items
        return context
