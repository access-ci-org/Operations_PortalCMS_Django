"""
Workflow management for integration news items.
Handles state transitions: draft -> published
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from .models import IntegrationNews


def can_publish(news, user, permission_codename):
    """Check if user can publish news"""
    return news.status == 'draft' and user.has_perm(permission_codename)


def can_unpublish(news, user, permission_codename):
    """Check if user can unpublish news"""
    return news.status == 'published' and user.has_perm(permission_codename)


@login_required
@permission_required('integration_news.can_publish_integrationnews',
                     login_url=reverse_lazy('portal:unprivileged'))
@require_POST
def publish_integration_news(request, pk):
    """Publish a draft integration news item"""
    news = get_object_or_404(IntegrationNews, pk=pk)

    if not can_publish(news, request.user, 'integration_news.can_publish_integrationnews'):
        messages.error(request, 'You cannot publish this news.')
        return redirect('integration_news:integration_news')

    news.status = 'published'
    news.published_by = request.user
    news.published_at = timezone.now()
    news.save()
    messages.success(request, 'News published successfully!')
    return redirect('integration_news:integration_news')


@login_required
@permission_required('integration_news.can_publish_integrationnews',
                     login_url=reverse_lazy('portal:unprivileged'))
@require_POST
def unpublish_integration_news(request, pk):
    """Unpublish integration news (return to draft)"""
    news = get_object_or_404(IntegrationNews, pk=pk)

    if not can_unpublish(news, request.user, 'integration_news.can_publish_integrationnews'):
        messages.error(request, 'You cannot unpublish this news.')
        return redirect('integration_news:integration_news')

    news.status = 'draft'
    news.save()
    messages.info(request, 'News unpublished and returned to draft.')
    return redirect('integration_news:integration_news')
