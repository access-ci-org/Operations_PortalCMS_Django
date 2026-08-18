from datetime import timezone as datetime_timezone
from zoneinfo import ZoneInfo

from django.db.models import F
from django.urls import reverse
from django.utils import timezone

from .models import SystemStatusNews


API_TIME_ZONE = ZoneInfo('America/Chicago')


def _format_timestamp(value):
    """Format a datetime like the legacy Drupal infrastructure-news API."""
    if value is None:
        return ''
    if timezone.is_naive(value):
        value = timezone.make_aware(value, datetime_timezone.utc)
    return timezone.localtime(value, API_TIME_ZONE).strftime('%Y-%m-%dT%H:%M:%S%z')


def get_public_news_queryset():
    """Return records shared by the public page and compatibility API.

    Callers apply presentation-specific ordering: the HTML page keeps the model's
    newest-first ordering, while the legacy API is organized by ``outage_id``.
    """
    return SystemStatusNews.objects.filter(status='published', is_active=True)


def _distribution_options(news):
    options = []
    if news.email_list:
        options.append('Email only subscribers')
    elif news.send_email:
        options.append('Email everyone with access')
    if news.post_to_slack:
        options.append('Post to Slack')
    return ', '.join(options)


def _affected_infrastructure(news):
    return [
        {'infra_resourceid': resource_id}
        for resource_id in news.get_affected_infrastructure_values()
    ]


def _news_item_to_dict(news, request):
    return {
        'subject': news.subject,
        'type': news.get_infrastructure_news_type_display(),
        'content': news.content,
        'start_timestamp': _format_timestamp(news.start_datetime),
        'end_timestamp': _format_timestamp(news.end_datetime),
        'web_url': request.build_absolute_uri(reverse('infrastructure_news:system_status_news')),
        'outage_id': str(news.outage_id) if news.outage_id is not None else None,
        'distribution_options': _distribution_options(news),
        'affected_infrastructure': _affected_infrastructure(news),
    }


def get_public_news_feed(request):
    news_items = get_public_news_queryset().prefetch_related(
        'affected_infrastructure_items'
    ).order_by(F('outage_id').asc(nulls_last=True), 'pk')
    return [_news_item_to_dict(news, request) for news in news_items]
