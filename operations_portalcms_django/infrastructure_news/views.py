from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.cache import cache_page
from django.views.decorators.http import require_safe
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Prefetch
from .models import SystemStatusNews
from .forms import SystemStatusNewsForm
from . import services


def system_status_news(request):
    """System and Infrastructure Status News listing page"""
    infrastructure_prefetch = Prefetch(
        'affected_infrastructure_items',
        queryset=SystemStatusNews.affected_infrastructure_items.rel.model.objects.order_by(
            'resource_descriptive_name'
        ),
    )

    if request.user.is_authenticated and (
        request.user.has_perm('infrastructure_news.change_systemstatusnews') or
        request.user.has_perm('infrastructure_news.can_review_systemstatusnews') or
        request.user.has_perm('infrastructure_news.can_publish_systemstatusnews')
    ):
        news_items = SystemStatusNews.objects.filter(is_active=True)
    else:
        news_items = services.get_public_news_queryset()

    news_items = news_items.select_related('author', 'reviewer').prefetch_related(infrastructure_prefetch)
    paginator = Paginator(news_items, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portal/infrastructure_news.html', {
        'page': 'system_status_news',
        'system_status_news': page_obj,
        'page_obj': page_obj,
        'can_review': request.user.has_perm('infrastructure_news.can_review_systemstatusnews') if request.user.is_authenticated else False,
        'can_publish': request.user.has_perm('infrastructure_news.can_publish_systemstatusnews') if request.user.is_authenticated else False,
    })


@login_required
@permission_required('infrastructure_news.add_systemstatusnews', login_url=reverse_lazy('portal:unprivileged'))
def add_system_status_news(request):
    """Add new system and infrastructure status news item"""
    can_publish = request.user.is_superuser or request.user.has_perm('infrastructure_news.can_publish_systemstatusnews')

    if request.method == 'POST':
        form = SystemStatusNewsForm(request.POST)
        if form.is_valid():
            news = form.save(commit=False)
            news.author = request.user
            if 'publish' in request.POST and can_publish:
                news.status = 'published'
                news.published_by = request.user
                news.published_at = timezone.now()
                messages.success(request, 'System and infrastructure status news published successfully!')
            else:
                news.status = 'draft'
                messages.success(request, 'System and infrastructure status news created as draft. Submit for review when ready.')
            news.save()
            form.save_related_fields(news)
            return redirect('infrastructure_news:system_status_news')
    else:
        form = SystemStatusNewsForm()

    return render(request, 'portal/add_system_status_news.html', {
        'page': 'system_status_news',
        'form': form,
        'can_publish': can_publish,
    })


@login_required
@permission_required('infrastructure_news.change_systemstatusnews', login_url=reverse_lazy('portal:unprivileged'))
def update_system_status_news(request, pk):
    """Update existing system and infrastructure status news item"""
    news = get_object_or_404(SystemStatusNews, pk=pk)
    can_publish = request.user.is_superuser or request.user.has_perm('infrastructure_news.can_publish_systemstatusnews')

    if request.method == 'POST':
        form = SystemStatusNewsForm(request.POST, instance=news)
        if form.is_valid():
            news = form.save(commit=False)
            if 'publish' in request.POST and can_publish:
                news.status = 'published'
                news.published_by = request.user
                news.published_at = timezone.now()
                news.save()
                messages.success(request, 'System and infrastructure status news updated and published successfully!')
            else:
                news.save()
                messages.success(request, 'System and infrastructure status news updated successfully!')
            form.save_related_fields(news)
            return redirect('infrastructure_news:system_status_news')
    else:
        form = SystemStatusNewsForm(instance=news)

    return render(request, 'portal/update_system_status_news.html', {
        'page': 'system_status_news',
        'news': news,
        'form': form,
        'can_publish': can_publish,
    })


@require_safe
@cache_page(60 * 15)
def api_infrastructure_news(request):
    """Public JSON feed of published System Status News, matching the shape of the
    legacy Drupal /api/infrastructure_news endpoint for downstream consumers."""
    if request.method not in ('GET', 'HEAD'):
        from django.http import HttpResponseNotAllowed
        return HttpResponseNotAllowed(['GET', 'HEAD'])
    return JsonResponse(services.get_public_news_feed(request), safe=False)
