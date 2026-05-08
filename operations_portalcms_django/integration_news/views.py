from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.urls import reverse_lazy
from django.utils import timezone
from django.db.models import Prefetch
from .models import IntegrationNews
from .forms import IntegrationNewsForm


def integration_news(request):
    """Integration News listing page"""
    element_prefetch = Prefetch(
        'affected_elements',
        queryset=IntegrationNews.affected_elements.rel.model.objects.order_by('label'),
    )

    if request.user.is_authenticated and (
        request.user.has_perm('integration_news.change_integrationnews') or
        request.user.has_perm('integration_news.can_review_integrationnews') or
        request.user.has_perm('integration_news.can_publish_integrationnews')
    ):
        news_items = IntegrationNews.objects.filter(is_active=True)
    else:
        news_items = IntegrationNews.objects.filter(is_active=True, status='published')

    news_items = news_items.select_related('author', 'reviewer').prefetch_related(element_prefetch)
    paginator = Paginator(news_items, 20)
    page_obj = paginator.get_page(request.GET.get('page'))

    return render(request, 'portal/integration_news.html', {
        'page': 'integration_news',
        'integration_news': page_obj,
        'page_obj': page_obj,
        'can_review': request.user.has_perm('integration_news.can_review_integrationnews') if request.user.is_authenticated else False,
        'can_publish': request.user.has_perm('integration_news.can_publish_integrationnews') if request.user.is_authenticated else False,
    })


@login_required
@permission_required('integration_news.add_integrationnews', login_url=reverse_lazy('portal:unprivileged'))
def add_integration_news(request):
    """Add new integration news item"""
    can_publish = request.user.is_superuser or request.user.has_perm('integration_news.can_publish_integrationnews')

    if request.method == 'POST':
        form = IntegrationNewsForm(request.POST)
        if form.is_valid():
            news = form.save(commit=False)
            news.author = request.user
            news.is_active = True
            news.news_type = form.cleaned_data.get('news_type', '')
            news.effective_date = form.cleaned_data.get('effective_date')
            news.expiration_date = form.cleaned_data.get('expiration_date')
            if 'publish' in request.POST and can_publish:
                news.status = 'published'
                news.published_by = request.user
                news.published_at = timezone.now()
                messages.success(request, 'Integration news published successfully!')
            else:
                news.status = 'draft'
                messages.success(request, 'Integration news created as draft. Submit for review when ready.')
            news.save()
            form.save_related_fields(news)
            return redirect('integration_news:integration_news')
    else:
        form = IntegrationNewsForm()

    return render(request, 'portal/add_integration_news.html', {
        'page': 'integration_news',
        'form': form,
        'can_publish': can_publish,
    })


@login_required
@permission_required('integration_news.change_integrationnews', login_url=reverse_lazy('portal:unprivileged'))
def update_integration_news(request, pk):
    """Update existing integration news item"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    can_publish = request.user.is_superuser or request.user.has_perm('integration_news.can_publish_integrationnews')

    if request.method == 'POST':
        form = IntegrationNewsForm(request.POST, instance=news)
        if form.is_valid():
            news = form.save(commit=False)
            news.news_type = form.cleaned_data.get('news_type', '')
            news.effective_date = form.cleaned_data.get('effective_date')
            news.expiration_date = form.cleaned_data.get('expiration_date')
            if 'publish' in request.POST and can_publish:
                news.status = 'published'
                news.published_by = request.user
                news.published_at = timezone.now()
                news.save()
                messages.success(request, 'Integration news updated and published successfully!')
            else:
                news.save()
                messages.success(request, 'Integration news updated successfully!')
            form.save_related_fields(news)
            return redirect('integration_news:integration_news')
    else:
        form = IntegrationNewsForm(instance=news, initial={
            'news_type': news.news_type,
            'effective_date': news.effective_date,
            'expiration_date': news.expiration_date,
        })

    return render(request, 'portal/update_integration_news.html', {
        'page': 'integration_news',
        'news': news,
        'form': form,
        'can_publish': can_publish,
    })
