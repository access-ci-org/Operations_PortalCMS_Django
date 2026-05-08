"""
Workflow management for infrastructure (system status) news items.
Handles state transitions: draft → pending_review → approved → published
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy
from .models import SystemStatusNews


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
def submit_systemstatus_for_review(request, pk):
    """Submit system status news for review"""
    news = get_object_or_404(SystemStatusNews, pk=pk)

    if not can_submit_for_review(news, request.user):
        messages.error(request, 'You cannot submit this news for review.')
        return redirect('infrastructure_news:system_status_news')

    news.status = 'pending_review'
    news.save()
    messages.success(request, 'News submitted for review successfully!')
    return redirect('infrastructure_news:system_status_news')


@login_required
@permission_required('infrastructure_news.can_review_systemstatusnews',
                     login_url=reverse_lazy('portal:unprivileged'))
def approve_systemstatus_news(request, pk):
    """Approve system status news"""
    news = get_object_or_404(SystemStatusNews, pk=pk)

    if not can_approve_or_reject(news, request.user, 'infrastructure_news.can_review_systemstatusnews'):
        messages.error(request, 'You cannot approve this news.')
        return redirect('infrastructure_news:system_status_news')

    news.status = 'approved'
    news.reviewer = request.user
    news.reviewed_at = timezone.now()
    news.save()
    messages.success(request, 'News approved successfully!')
    return redirect('infrastructure_news:system_status_news')


@login_required
@permission_required('infrastructure_news.can_review_systemstatusnews',
                     login_url=reverse_lazy('portal:unprivileged'))
def reject_systemstatus_news(request, pk):
    """Reject system status news with comments"""
    news = get_object_or_404(SystemStatusNews, pk=pk)

    if not can_approve_or_reject(news, request.user, 'infrastructure_news.can_review_systemstatusnews'):
        messages.error(request, 'You cannot reject this news.')
        return redirect('infrastructure_news:system_status_news')

    if request.method == 'POST':
        comments = request.POST.get('review_comments', '')
        news.status = 'rejected'
        news.reviewer = request.user
        news.reviewed_at = timezone.now()
        news.review_comments = comments
        news.save()
        messages.warning(request, 'News rejected. Author has been notified.')
        return redirect('infrastructure_news:system_status_news')

    return redirect('infrastructure_news:update_system_status_news', pk=pk)


@login_required
@permission_required('infrastructure_news.can_publish_systemstatusnews',
                     login_url=reverse_lazy('portal:unprivileged'))
def publish_systemstatus_news(request, pk):
    """Publish approved system status news"""
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
def unpublish_systemstatus_news(request, pk):
    """Unpublish system status news (return to draft)"""
    news = get_object_or_404(SystemStatusNews, pk=pk)

    if not can_unpublish(news, request.user):
        messages.error(request, 'You cannot unpublish this news.')
        return redirect('infrastructure_news:system_status_news')

    news.status = 'draft'
    news.save()
    messages.info(request, 'News unpublished and returned to draft.')
    return redirect('infrastructure_news:system_status_news')
