"""
Workflow management for infrastructure (system status) news items.
Handles state transitions: draft -> published
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from .models import SystemStatusNews


def can_publish(news, user, permission_codename):
    """Check if user can publish news"""
    return news.status == 'draft' and user.has_perm(permission_codename)


def can_unpublish(news, user, permission_codename):
    """Check if user can unpublish news"""
    return news.status == 'published' and user.has_perm(permission_codename)


@login_required
@permission_required('infrastructure_news.can_publish_systemstatusnews',
                     login_url=reverse_lazy('portal:unprivileged'))
@require_POST
def publish_systemstatus_news(request, pk):
    """Publish a draft system status news item"""
    news = get_object_or_404(SystemStatusNews, pk=pk)

    if not can_publish(news, request.user, 'infrastructure_news.can_publish_systemstatusnews'):
        messages.error(request, 'You cannot publish this news.')
        return redirect('infrastructure_news:system_status_news')

    news.status = 'published'
    news.published_by = request.user
    news.published_at = timezone.now()
    news.save()
    messages.success(request, 'News published successfully!')
    return redirect('infrastructure_news:system_status_news')


@login_required
@permission_required('infrastructure_news.can_publish_systemstatusnews',
                     login_url=reverse_lazy('portal:unprivileged'))
@require_POST
def unpublish_systemstatus_news(request, pk):
    """Unpublish system status news (return to draft)"""
    news = get_object_or_404(SystemStatusNews, pk=pk)

    if not can_unpublish(news, request.user, 'infrastructure_news.can_publish_systemstatusnews'):
        messages.error(request, 'You cannot unpublish this news.')
        return redirect('infrastructure_news:system_status_news')

    news.status = 'draft'
    news.save()
    messages.info(request, 'News unpublished and returned to draft.')
    return redirect('infrastructure_news:system_status_news')
