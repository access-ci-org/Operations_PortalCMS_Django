from django.db.models import F
from django.urls import reverse

from .models import IntegrationNews


def get_public_news_queryset():
    """Return records shared by the public page and compatibility API."""
    return IntegrationNews.objects.filter(status='published', is_active=True)


def _affected_integration_element(news):
    return [
        {'title': label}
        for label in news.get_affected_element_labels()
    ]


def _news_item_to_dict(news, request):
    return {
        'subject': news.title,
        'type': news.get_news_type_label(),
        'content': news.content,
        'effective_date': news.effective_date.isoformat() if news.effective_date else '',
        'web_url': request.build_absolute_uri(reverse('integration_news:integration_news')),
        'integration_news_id': str(news.integration_news_id) if news.integration_news_id is not None else None,
        'distribution_options': '',
        'affected_integration_element': _affected_integration_element(news),
    }


def get_public_news_feed(request):
    news_items = get_public_news_queryset().prefetch_related(
        'affected_elements'
    ).order_by(F('integration_news_id').asc(nulls_last=True), 'pk')
    return [_news_item_to_dict(news, request) for news in news_items]
