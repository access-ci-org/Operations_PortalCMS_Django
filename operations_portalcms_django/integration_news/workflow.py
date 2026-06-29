"""
Workflow management for integration news items.
Handles state transitions: draft → pending_review → approved → published
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy
from django.views.decorators.http import require_POST
from .models import IntegrationNews


def can_submit_for_review(news, user):
    """Check if user can submit news for review"""
    return news.status == 'draft' and news.author == user


def can_approve_or_reject(news, user, permission_codename):
    """Check if user can approve or reject news"""
    return news.status == 'pending_review' and user.has_perm(permission_codename)


def can_publish(news, user, permission_codename):
    """Check if user can publish news"""
    return news.status in ('approved', 'pending_review') and user.has_perm(permission_codename)


def can_unpublish(news, user):
    """Check if user can unpublish news"""
    return news.status == 'published' and (news.author == user or user.is_superuser)


@login_required
@require_POST
def submit_integration_for_review(request, pk):
    """Submit integration news for review"""
    news = get_object_or_404(IntegrationNews, pk=pk)

    if not can_submit_for_review(news, request.user):
        messages.error(request, 'You cannot submit this news for review.')
        return redirect('integration_news:integration_news')

    news.status = 'pending_review'
    news.save()
    messages.success(request, 'News submitted for review successfully!')
    return redirect('integration_news:integration_news')


@login_required
@permission_required('integration_news.can_review_integrationnews',
                     login_url=reverse_lazy('portal:unprivileged'))
@require_POST
def approve_integration_news(request, pk):
    """Approve integration news"""
    news = get_object_or_404(IntegrationNews, pk=pk)

    if not can_approve_or_reject(news, request.user, 'integration_news.can_review_integrationnews'):
        messages.error(request, 'You cannot approve this news.')
        return redirect('integration_news:integration_news')

    news.status = 'approved'
    news.reviewer = request.user
    news.reviewed_at = timezone.now()
    news.save()
    messages.success(request, 'News approved successfully!')
    return redirect('integration_news:integration_news')


@login_required
@permission_required('integration_news.can_review_integrationnews',
                     login_url=reverse_lazy('portal:unprivileged'))
@require_POST
def reject_integration_news(request, pk):
    """Reject integration news with comments"""
    news = get_object_or_404(IntegrationNews, pk=pk)

    if not can_approve_or_reject(news, request.user, 'integration_news.can_review_integrationnews'):
        messages.error(request, 'You cannot reject this news.')
        return redirect('integration_news:integration_news')

    comments = request.POST.get('review_comments', '')
    news.status = 'rejected'
    news.reviewer = request.user
    news.reviewed_at = timezone.now()
    news.review_comments = comments
    news.save()
    messages.warning(request, 'News rejected. Author has been notified.')
    return redirect('integration_news:integration_news')


@login_required
@permission_required('integration_news.can_publish_integrationnews',
                     login_url=reverse_lazy('portal:unprivileged'))
@require_POST
def publish_integration_news(request, pk):
    """Publish approved integration news"""
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
@require_POST
def unpublish_integration_news(request, pk):
    """Unpublish integration news (return to draft)"""
    news = get_object_or_404(IntegrationNews, pk=pk)

    if not can_unpublish(news, request.user):
        messages.error(request, 'You cannot unpublish this news.')
        return redirect('integration_news:integration_news')

    news.status = 'draft'
    news.save()
    messages.info(request, 'News unpublished and returned to draft.')
    return redirect('integration_news:integration_news')
