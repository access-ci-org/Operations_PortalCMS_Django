from cms.plugin_base import CMSPluginBase
from cms.plugin_pool import plugin_pool
from cms.models.pluginmodel import CMSPlugin
from .models import IntegrationNewsItemPlugin


@plugin_pool.register_plugin
class IntegrationNewsItemPluginPublisher(CMSPluginBase):
    model = IntegrationNewsItemPlugin
    name = "Integration News Item"
    render_template = "portal/plugins/integration_news_item.html"
    cache = False
    fieldsets = [(None, {'fields': ('title', 'content', 'author')})]

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        context['instance'] = instance
        return context


@plugin_pool.register_plugin
class IntegrationNewsFeedPlugin(CMSPluginBase):
    model = CMSPlugin
    name = "Integration News Feed"
    render_template = "portal/plugins/integration_news_feed.html"
    cache = False
    allow_children = True
    child_classes = ['IntegrationNewsItemPluginPublisher']

    def render(self, context, instance, placeholder):
        context = super().render(context, instance, placeholder)
        children = instance.child_plugin_instances or []
        news_items = [c for c in children if isinstance(c, IntegrationNewsItemPlugin)]
        news_items.sort(key=lambda x: x.published_date, reverse=True)
        context['news_items'] = news_items
        return context
