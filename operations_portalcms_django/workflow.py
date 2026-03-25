"""
Workflow management for news items.
Handles state transitions: draft → pending_review → approved → published
"""
from django.shortcuts import get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden
from .models import SystemStatusNews, IntegrationNews


def can_submit_for_review(news, user):
    """Check if user can submit news for review"""
    return news.status == 'draft' and news.author == user


def can_approve_or_reject(news, user, permission_codename):
    """Check if user can approve or reject news"""
    return news.status == 'pending_review' and user.has_perm(permission_codename)


def can_publish(news, user, permission_codename):
    """Check if user can publish news"""
    # Users with publish permission can publish from either 'approved' or 'pending_review'
    # This allows publishers to bypass the approval step
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
        return redirect('operations_portalcms_django:system_status_news')
    
    news.status = 'pending_review'
    news.save()
    messages.success(request, 'News submitted for review successfully!')
    return redirect('operations_portalcms_django:system_status_news')


@login_required
@permission_required('operations_portalcms_django.can_review_systemstatusnews', 
                     login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def approve_systemstatus_news(request, pk):
    """Approve system status news"""
    news = get_object_or_404(SystemStatusNews, pk=pk)
    
    if not can_approve_or_reject(news, request.user, 'operations_portalcms_django.can_review_systemstatusnews'):
        messages.error(request, 'You cannot approve this news.')
        return redirect('operations_portalcms_django:system_status_news')
    
    news.status = 'approved'
    news.reviewer = request.user
    news.reviewed_at = timezone.now()
    news.save()
    messages.success(request, 'News approved successfully!')
    return redirect('operations_portalcms_django:system_status_news')


@login_required
@permission_required('operations_portalcms_django.can_review_systemstatusnews',
                     login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def reject_systemstatus_news(request, pk):
    """Reject system status news with comments"""
    news = get_object_or_404(SystemStatusNews, pk=pk)
    
    if not can_approve_or_reject(news, request.user, 'operations_portalcms_django.can_review_systemstatusnews'):
        messages.error(request, 'You cannot reject this news.')
        return redirect('operations_portalcms_django:system_status_news')
    
    if request.method == 'POST':
        comments = request.POST.get('review_comments', '')
        news.status = 'rejected'
        news.reviewer = request.user
        news.reviewed_at = timezone.now()
        news.review_comments = comments
        news.save()
        messages.warning(request, 'News rejected. Author has been notified.')
        return redirect('operations_portalcms_django:system_status_news')
    
    # If GET request, show rejection form (handled in template)
    return redirect('operations_portalcms_django:update_system_status_news', pk=pk)


@login_required
@permission_required('operations_portalcms_django.can_publish_systemstatusnews',
                     login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def publish_systemstatus_news(request, pk):
    """Publish approved system status news"""
    news = get_object_or_404(SystemStatusNews, pk=pk)
    
    if not can_publish(news, request.user, 'operations_portalcms_django.can_publish_systemstatusnews'):
        messages.error(request, 'You cannot publish this news.')
        return redirect('operations_portalcms_django:system_status_news')
    
    news.status = 'published'
    news.published_by = request.user
    news.published_at = timezone.now()
    news.save()
    messages.success(request, 'News published successfully!')
    return redirect('operations_portalcms_django:system_status_news')


@login_required
def unpublish_systemstatus_news(request, pk):
    """Unpublish system status news (return to draft)"""
    news = get_object_or_404(SystemStatusNews, pk=pk)
    
    if not can_unpublish(news, request.user):
        messages.error(request, 'You cannot unpublish this news.')
        return redirect('operations_portalcms_django:system_status_news')
    
    news.status = 'draft'
    news.save()
    messages.info(request, 'News unpublished and returned to draft.')
    return redirect('operations_portalcms_django:system_status_news')


# Integration News workflow actions

@login_required
def submit_integration_for_review(request, pk):
    """Submit integration news for review"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    
    if not can_submit_for_review(news, request.user):
        messages.error(request, 'You cannot submit this news for review.')
        return redirect('operations_portalcms_django:integration_news')
    
    news.status = 'pending_review'
    news.save()
    messages.success(request, 'News submitted for review successfully!')
    return redirect('operations_portalcms_django:integration_news')


@login_required
@permission_required('operations_portalcms_django.can_review_integrationnews',
                     login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def approve_integration_news(request, pk):
    """Approve integration news"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    
    if not can_approve_or_reject(news, request.user, 'operations_portalcms_django.can_review_integrationnews'):
        messages.error(request, 'You cannot approve this news.')
        return redirect('operations_portalcms_django:integration_news')
    
    news.status = 'approved'
    news.reviewer = request.user
    news.reviewed_at = timezone.now()
    news.save()
    messages.success(request, 'News approved successfully!')
    return redirect('operations_portalcms_django:integration_news')


@login_required
@permission_required('operations_portalcms_django.can_review_integrationnews',
                     login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def reject_integration_news(request, pk):
    """Reject integration news with comments"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    
    if not can_approve_or_reject(news, request.user, 'operations_portalcms_django.can_review_integrationnews'):
        messages.error(request, 'You cannot reject this news.')
        return redirect('operations_portalcms_django:integration_news')
    
    if request.method == 'POST':
        comments = request.POST.get('review_comments', '')
        news.status = 'rejected'
        news.reviewer = request.user
        news.reviewed_at = timezone.now()
        news.review_comments = comments
        news.save()
        messages.warning(request, 'News rejected. Author has been notified.')
        return redirect('operations_portalcms_django:integration_news')
    
    return redirect('operations_portalcms_django:update_integration_news', pk=pk)


@login_required
@permission_required('operations_portalcms_django.can_publish_integrationnews',
                     login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def publish_integration_news(request, pk):
    """Publish approved integration news"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    
    if not can_publish(news, request.user, 'operations_portalcms_django.can_publish_integrationnews'):
        messages.error(request, 'You cannot publish this news.')
        return redirect('operations_portalcms_django:integration_news')
    
    news.status = 'published'
    news.published_by = request.user
    news.published_at = timezone.now()
    news.save()
    messages.success(request, 'News published successfully!')
    return redirect('operations_portalcms_django:integration_news')


@login_required
def unpublish_integration_news(request, pk):
    """Unpublish integration news (return to draft)"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    
    if not can_unpublish(news, request.user):
        messages.error(request, 'You cannot unpublish this news.')
        return redirect('operations_portalcms_django:integration_news')
    
    news.status = 'draft'
    news.save()
    messages.info(request, 'News unpublished and returned to draft.')
    return redirect('operations_portalcms_django:integration_news')

