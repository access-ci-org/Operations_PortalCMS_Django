from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.views.decorators.cache import cache_page
from django.urls import reverse_lazy
from .models import SystemStatusNews, IntegrationNews
from .forms import SystemStatusNewsForm, IntegrationNewsForm
import requests
from collections import defaultdict


def index(request):
    """Operations Portal landing page"""
    context = {
        'page': 'index',
    }
    return render(request, 'operations_portalcms_django/index.html', context)


def system_status_news(request):
    """System and Infrastructure Status News listing page"""
    news_items = SystemStatusNews.objects.filter(is_active=True)
    context = {
        'page': 'system_status_news',
        'system_status_news': news_items,
    }
    return render(request, 'operations_portalcms_django/infrastructure_news.html', context)


def integration_news(request):
    """Integration News listing page"""
    news_items = IntegrationNews.objects.filter(is_active=True)
    context = {
        'page': 'integration_news',
        'integration_news': news_items,
    }
    return render(request, 'operations_portalcms_django/integration_news.html', context)


# News management views with permission checks

@login_required
@permission_required('operations_portalcms_django.add_systemstatusnews', login_url=reverse_lazy('web:unprivileged'))
def add_system_status_news(request):
    """Add new system and infrastructure status news item"""
    if request.method == 'POST':
        form = SystemStatusNewsForm(request.POST)
        if form.is_valid():
            news = form.save(commit=False)
            news.author = request.user
            news.save()
            messages.success(request, 'System and infrastructure status news added successfully!')
            return redirect('operations_portalcms_django:system_status_news')
    else:
        form = SystemStatusNewsForm()
    
    context = {
        'page': 'system_status_news',
        'form': form,
    }
    return render(request, 'operations_portalcms_django/add_system_status_news.html', context)


@login_required
@permission_required('operations_portalcms_django.change_systemstatusnews', login_url=reverse_lazy('web:unprivileged'))
def update_system_status_news(request, pk):
    """Update existing system and infrastructure status news item"""
    news = get_object_or_404(SystemStatusNews, pk=pk)
    
    if request.method == 'POST':
        form = SystemStatusNewsForm(request.POST, instance=news)
        if form.is_valid():
            form.save()
            messages.success(request, 'System and infrastructure status news updated successfully!')
            return redirect('operations_portalcms_django:system_status_news')
    else:
        form = SystemStatusNewsForm(instance=news)
    
    context = {
        'page': 'system_status_news',
        'news': news,
        'form': form,
    }
    return render(request, 'operations_portalcms_django/update_system_status_news.html', context)


@login_required
@permission_required('operations_portalcms_django.add_integrationnews', login_url=reverse_lazy('web:unprivileged'))
def add_integration_news(request):
    """Add new integration news item"""
    if request.method == 'POST':
        form = IntegrationNewsForm(request.POST)
        if form.is_valid():
            news = form.save(commit=False)
            news.author = request.user
            # Save form data for fields not in the model
            news.news_type = form.cleaned_data.get('news_type', '')
            news.affected_element = form.cleaned_data.get('affected_element', '')
            news.effective_date = form.cleaned_data.get('effective_date')
            news.expiration_date = form.cleaned_data.get('expiration_date')
            news.save()
            messages.success(request, 'Integration news added successfully!')
            return redirect('operations_portalcms_django:integration_news')
    else:
        form = IntegrationNewsForm()
    
    context = {
        'page': 'integration_news',
        'form': form,
    }
    return render(request, 'operations_portalcms_django/add_integration_news.html', context)


@login_required
@permission_required('operations_portalcms_django.change_integrationnews', login_url=reverse_lazy('web:unprivileged'))
def update_integration_news(request, pk):
    """Update existing integration news item"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    
    if request.method == 'POST':
        form = IntegrationNewsForm(request.POST, instance=news)
        if form.is_valid():
            news = form.save(commit=False)
            # Save form data for fields not in the model
            news.news_type = form.cleaned_data.get('news_type', '')
            news.affected_element = form.cleaned_data.get('affected_element', '')
            news.effective_date = form.cleaned_data.get('effective_date')
            news.expiration_date = form.cleaned_data.get('expiration_date')
            news.save()
            messages.success(request, 'Integration news updated successfully!')
            return redirect('operations_portalcms_django:integration_news')
    else:
        # Pre-populate form with existing data
        initial_data = {
            'news_type': news.news_type,
            'affected_element': news.affected_element,
            'effective_date': news.effective_date,
            'expiration_date': news.expiration_date,
        }
        form = IntegrationNewsForm(instance=news, initial=initial_data)
    
    context = {
        'page': 'integration_news',
        'news': news,
        'form': form,
    }
    return render(request, 'operations_portalcms_django/update_integration_news.html', context)


@cache_page(60 * 15)  # Cache for 15 minutes
def access_allocated_resources(request):
    """Display ACCESS allocated resources from API"""
    api_url = 'https://operations-api.access-ci.org/wh2/cider/v1/access-active/'
    
    resources_by_org = defaultdict(list)
    error_message = None
    
    try:
        headers = {'Accept': 'application/json'}
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        # Check if response has content
        if not response.content:
            error_message = "API returned empty response"
            resources_by_org = {}
        else:
            try:
                data = response.json()
                
                # Group resources by organization
                for resource in data.get('results', []):
                    # Use organization name from the resource provider organization field
                    org_name = resource.get('organization_name', 'Unknown Organization')
                    if not org_name or org_name.strip() == '':
                        org_name = 'Unknown Organization'
                    resources_by_org[org_name].append(resource)
                
                # Sort organizations alphabetically
                resources_by_org = dict(sorted(resources_by_org.items()))
                
            except ValueError as json_err:
                error_message = f"Invalid JSON response: {str(json_err)}"
                resources_by_org = {}
        
    except requests.RequestException as e:
        error_message = f"Unable to fetch resources: {str(e)}"
        resources_by_org = {}
    
    context = {
        'page': 'access_allocated',
        'resources_by_org': resources_by_org,
        'error_message': error_message,
    }
    return render(request, 'operations_portalcms_django/access_allocated.html', context)


@cache_page(60 * 15)  # Cache for 15 minutes
def resource_detail(request, node_id):
    """Display detailed information for a single resource from CIDER API"""
    api_url = f'https://operations-api.access-ci.org/wh2/cider/v1/cider_resource_id/{node_id}/'
    
    resource = None
    error_message = None
    
    try:
        headers = {'Accept': 'application/json'}
        response = requests.get(api_url, headers=headers, timeout=10)
        response.raise_for_status()
        
        if not response.content:
            error_message = "Resource not found"
        else:
            try:
                data = response.json()
                # Extract resource from 'results' key
                resource = data.get('results', {})
                if not resource:
                    error_message = "Resource not found"
            except ValueError as json_err:
                error_message = f"Invalid JSON response: {str(json_err)}"
        
    except requests.RequestException as e:
        error_message = f"Unable to fetch resource details: {str(e)}"
    
    context = {
        'page': 'resource_detail',
        'resource': resource,
        'error_message': error_message,
    }
    return render(request, 'operations_portalcms_django/resource_detail.html', context)
