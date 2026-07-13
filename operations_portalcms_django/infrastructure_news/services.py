from django.urls import reverse

from .models import SystemStatusNews


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
        'start_timestamp': news.start_datetime.strftime('%Y-%m-%dT%H:%M:%S%z') if news.start_datetime else '',
        'end_timestamp': news.end_datetime.strftime('%Y-%m-%dT%H:%M:%S%z') if news.end_datetime else '',
        'web_url': request.build_absolute_uri(reverse('infrastructure_news:system_status_news')),
        'outage_id': str(news.pk),
        'distribution_options': _distribution_options(news),
        'affected_infrastructure': _affected_infrastructure(news),
    }


def get_public_news_feed(request):
    news_items = SystemStatusNews.objects.filter(
        status='published', is_active=True
    ).prefetch_related('affected_infrastructure_items').order_by('-start_datetime')
    return [_news_item_to_dict(news, request) for news in news_items]
