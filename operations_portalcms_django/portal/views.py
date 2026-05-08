from django.shortcuts import redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.views.decorators.http import require_POST
from django.urls import reverse_lazy
from django.http import HttpResponseForbidden
from django.shortcuts import render
from djangocms_versioning.helpers import remove_version_lock, version_list_url
from djangocms_versioning.models import Version


def unprivileged(request):
    """Error page for users without required permissions"""
    return render(request, 'web/unprivileged.html')


@staff_member_required(login_url=reverse_lazy('admin:login'))
@require_POST
def submit_page_draft_for_review(request, version_id):
    """Release a draft lock so another editor can review or publish it."""
    version = get_object_or_404(Version, pk=version_id)
    next_url = request.GET.get('next') or version_list_url(version.content)

    if version.state != 'draft':
        messages.error(request, 'Only draft versions can be submitted for review.')
        return redirect(next_url)

    can_unlock = request.user.has_perm('djangocms_versioning.delete_versionlock')
    owns_lock = version.locked_by_id == request.user.pk

    if not can_unlock and not owns_lock:
        return HttpResponseForbidden('You do not have permission to submit this draft for review.')

    if version.locked_by_id is None:
        messages.info(request, 'This draft is already available for review.')
        return redirect(next_url)

    remove_version_lock(version)
    messages.success(
        request,
        'Draft submitted for review. The draft lock has been released for reviewers.',
    )
    return redirect(next_url)


@login_required
@require_POST
def unlock_cms_page_draft(request, version_id):
    """Unlock a version lock and redirect back to the CMS page."""
    version = get_object_or_404(Version, pk=version_id)
    next_url = request.GET.get('next') or request.META.get('HTTP_REFERER') or '/'

    if not request.user.has_perm('djangocms_versioning.delete_versionlock'):
        return HttpResponseForbidden('You do not have permission to unlock this version.')

    if version.state != 'draft':
        messages.error(request, 'Only draft versions can be unlocked.')
        return redirect(next_url)

    if version.locked_by_id is None:
        messages.info(request, 'This version is already unlocked.')
        return redirect(next_url)

    remove_version_lock(version)
    messages.success(request, 'Version unlocked. You can now edit or publish it.')
    return redirect(next_url)
