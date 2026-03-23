from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.views.decorators.cache import cache_page
from django.urls import reverse_lazy
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.utils import timezone
from django.db.models import Prefetch
from .models import SystemStatusNews, IntegrationNews
from .forms import SystemStatusNewsForm, IntegrationNewsForm
import requests
from collections import defaultdict


def unprivileged(request):
    """Error page for users without required permissions"""
    return render(request, 'web/unprivileged.html')


def system_status_news(request):
    """System and Infrastructure Status News listing page"""
    infrastructure_prefetch = Prefetch(
        'affected_infrastructure_items',
        queryset=SystemStatusNews.affected_infrastructure_items.rel.model.objects.order_by(
            'resource_descriptive_name'
        ),
    )

    # Show only published news to non-authenticated users
    # Show all news to authenticated users with permissions
    if request.user.is_authenticated and (
        request.user.has_perm('operations_portalcms_django.change_systemstatusnews') or
        request.user.has_perm('operations_portalcms_django.can_review_systemstatusnews') or
        request.user.has_perm('operations_portalcms_django.can_publish_systemstatusnews')
    ):
        news_items = SystemStatusNews.objects.filter(is_active=True)
    else:
        news_items = SystemStatusNews.objects.filter(
            is_active=True,
            status='published',
        )

    news_items = news_items.select_related('author', 'reviewer').prefetch_related(
        infrastructure_prefetch
    )

    paginator = Paginator(news_items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page': 'system_status_news',
        'system_status_news': page_obj,
        'page_obj': page_obj,
        'can_review': request.user.has_perm('operations_portalcms_django.can_review_systemstatusnews') if request.user.is_authenticated else False,
        'can_publish': request.user.has_perm('operations_portalcms_django.can_publish_systemstatusnews') if request.user.is_authenticated else False,
    }
    return render(request, 'operations_portalcms_django/infrastructure_news.html', context)


def integration_news(request):
    """Integration News listing page"""
    element_prefetch = Prefetch(
        'affected_elements',
        queryset=IntegrationNews.affected_elements.rel.model.objects.order_by('label'),
    )

    # Show only published news to non-authenticated users
    # Show all news to authenticated users with permissions
    if request.user.is_authenticated and (
        request.user.has_perm('operations_portalcms_django.change_integrationnews') or
        request.user.has_perm('operations_portalcms_django.can_review_integrationnews') or
        request.user.has_perm('operations_portalcms_django.can_publish_integrationnews')
    ):
        news_items = IntegrationNews.objects.filter(is_active=True)
    else:
        news_items = IntegrationNews.objects.filter(
            is_active=True,
            status='published',
        )

    news_items = news_items.select_related('author', 'reviewer').prefetch_related(
        element_prefetch
    )

    paginator = Paginator(news_items, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'page': 'integration_news',
        'integration_news': page_obj,
        'page_obj': page_obj,
        'can_review': request.user.has_perm('operations_portalcms_django.can_review_integrationnews') if request.user.is_authenticated else False,
        'can_publish': request.user.has_perm('operations_portalcms_django.can_publish_integrationnews') if request.user.is_authenticated else False,
    }
    return render(request, 'operations_portalcms_django/integration_news.html', context)


# News management views with permission checks

@login_required
@permission_required('operations_portalcms_django.add_systemstatusnews', login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def add_system_status_news(request):
    """Add new system and infrastructure status news item"""
    can_publish = request.user.is_superuser or request.user.has_perm('operations_portalcms_django.can_publish_systemstatusnews')
    
    if request.method == 'POST':
        form = SystemStatusNewsForm(request.POST)
        if form.is_valid():
            news = form.save(commit=False)
            news.author = request.user
            
            # Check if user wants to publish directly
            if 'publish' in request.POST and can_publish:
                news.status = 'published'
                news.published_by = request.user
                news.published_at = timezone.now()
                messages.success(request, 'System and infrastructure status news published successfully!')
            else:
                news.status = 'draft'  # New news starts as draft
                messages.success(request, 'System and infrastructure status news created as draft. Submit for review when ready.')
            
            news.save()
            form.save_related_fields(news)
            return redirect('operations_portalcms_django:system_status_news')
    else:
        form = SystemStatusNewsForm()
    
    context = {
        'page': 'system_status_news',
        'form': form,
        'can_publish': can_publish,
    }
    return render(request, 'operations_portalcms_django/add_system_status_news.html', context)


@login_required
@permission_required('operations_portalcms_django.change_systemstatusnews', login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def update_system_status_news(request, pk):
    """Update existing system and infrastructure status news item"""
    news = get_object_or_404(SystemStatusNews, pk=pk)
    can_publish = request.user.is_superuser or request.user.has_perm('operations_portalcms_django.can_publish_systemstatusnews')
    
    if request.method == 'POST':
        form = SystemStatusNewsForm(request.POST, instance=news)
        if form.is_valid():
            news = form.save(commit=False)
            
            # Check if user wants to publish directly
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
            return redirect('operations_portalcms_django:system_status_news')
    else:
        form = SystemStatusNewsForm(instance=news)
    
    context = {
        'page': 'system_status_news',
        'news': news,
        'form': form,
        'can_publish': can_publish,
    }
    return render(request, 'operations_portalcms_django/update_system_status_news.html', context)


@login_required
@permission_required('operations_portalcms_django.add_integrationnews', login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def add_integration_news(request):
    """Add new integration news item"""
    can_publish = request.user.is_superuser or request.user.has_perm('operations_portalcms_django.can_publish_integrationnews')
    
    if request.method == 'POST':
        form = IntegrationNewsForm(request.POST)
        if form.is_valid():
            news = form.save(commit=False)
            news.author = request.user
            news.is_active = True  # New news is active by default
            # Save form data for fields not in the model
            news.news_type = form.cleaned_data.get('news_type', '')
            news.effective_date = form.cleaned_data.get('effective_date')
            news.expiration_date = form.cleaned_data.get('expiration_date')
            
            # Check if user wants to publish directly
            if 'publish' in request.POST and can_publish:
                news.status = 'published'
                news.published_by = request.user
                news.published_at = timezone.now()
                messages.success(request, 'Integration news published successfully!')
            else:
                news.status = 'draft'  # New news starts as draft
                messages.success(request, 'Integration news created as draft. Submit for review when ready.')
            
            news.save()
            form.save_related_fields(news)
            return redirect('operations_portalcms_django:integration_news')
    else:
        form = IntegrationNewsForm()
    
    context = {
        'page': 'integration_news',
        'form': form,
        'can_publish': can_publish,
    }
    return render(request, 'operations_portalcms_django/add_integration_news.html', context)


@login_required
@permission_required('operations_portalcms_django.change_integrationnews', login_url=reverse_lazy('operations_portalcms_django:unprivileged'))
def update_integration_news(request, pk):
    """Update existing integration news item"""
    news = get_object_or_404(IntegrationNews, pk=pk)
    can_publish = request.user.is_superuser or request.user.has_perm('operations_portalcms_django.can_publish_integrationnews')
    
    if request.method == 'POST':
        form = IntegrationNewsForm(request.POST, instance=news)
        if form.is_valid():
            news = form.save(commit=False)
            # Save form data for fields not in the model
            news.news_type = form.cleaned_data.get('news_type', '')
            news.effective_date = form.cleaned_data.get('effective_date')
            news.expiration_date = form.cleaned_data.get('expiration_date')
            
            # Check if user wants to publish directly
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
            return redirect('operations_portalcms_django:integration_news')
    else:
        initial_data = {
            'news_type': news.news_type,
            'effective_date': news.effective_date,
            'expiration_date': news.expiration_date,
        }
        form = IntegrationNewsForm(instance=news, initial=initial_data)
    
    context = {
        'page': 'integration_news',
        'news': news,
        'form': form,
        'can_publish': can_publish,
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
def access_online_services(request):
    """Display ACCESS online services from API"""
    api_url = 'https://operations-api.access-ci.org/wh2/cider/v1/access-online-services/'
    
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
        'page': 'access_online_services',
        'resources_by_org': resources_by_org,
        'error_message': error_message,
    }
    return render(request, 'operations_portalcms_django/access_online_services.html', context)


@cache_page(60 * 15)  # Cache for 15 minutes
def software_discovery(request):
    """Display software catalog from API with search, filtering, and pagination"""
    api_url = 'https://operations-api.access-ci.org/wh2/glue2/v1/software_fast/?format=json'
    
    software_list = []
    providers = {}
    error_message = None
    
    # Get search and filter parameters from request
    search_query = request.GET.get('q', '').strip()
    selected_provider = request.GET.get('provider', '')
    search_name = request.GET.get('search_name', 'on') == 'on'
    search_desc = request.GET.get('search_desc', 'on') == 'on'
    search_topics = request.GET.get('search_topics', 'on') == 'on'
    search_keywords = request.GET.get('search_keywords', 'on') == 'on'
    
    try:
        headers = {'Accept': 'application/json'}
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        if not response.content:
            error_message = "API returned empty response"
        else:
            try:
                data = response.json()
                # Handle both list and dict responses
                if isinstance(data, list):
                    results = data
                else:
                    results = data.get('results', [])
                
                # Count software by ResourceID (resource) for filters
                provider_counts = defaultdict(int)
                for item in results:
                    resource_id = item.get('ResourceID', 'Unknown Resource')
                    provider_counts[resource_id] += 1
                
                # Sort providers by count (descending)
                providers = dict(sorted(provider_counts.items(), key=lambda x: x[1], reverse=True))
                
                # Filter by selected provider (ResourceID)
                if selected_provider:
                    results = [item for item in results if item.get('ResourceID', '') == selected_provider]
                
                # Apply search filter
                if search_query:
                    filtered_results = []
                    query_lower = search_query.lower()
                    
                    for item in results:
                        match = False
                        if search_name and query_lower in item.get('AppName', '').lower():
                            match = True
                        if search_name and query_lower in item.get('AppVersion', '').lower():
                            match = True
                        if search_name and query_lower in item.get('ResourceID', '').lower():
                            match = True
                        if search_desc and item.get('Description') and query_lower in item.get('Description', '').lower():
                            match = True
                        if search_topics and item.get('Domain'):
                            for domain in item.get('Domain', []):
                                if query_lower in domain.lower():
                                    match = True
                                    break
                        if search_keywords and item.get('Keywords'):
                            for keyword in item.get('Keywords', []):
                                if query_lower in keyword.lower():
                                    match = True
                                    break
                        if search_desc:
                            handle_key = item.get('Handle', {}).get('HandleKey', '')
                            if query_lower in handle_key.lower():
                                match = True
                        
                        if match:
                            filtered_results.append(item)
                    
                    results = filtered_results
                
                software_list = results
                
            except ValueError as json_err:
                error_message = f"Invalid JSON response: {str(json_err)}"
        
    except requests.RequestException as e:
        error_message = f"Unable to fetch software data: {str(e)}"
    
    # Pagination - 25 items per page
    paginator = Paginator(software_list, 25)
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.get_page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.get_page(1)
    except EmptyPage:
        page_obj = paginator.get_page(paginator.num_pages)
    
    # Calculate viewing range
    start_index = (page_obj.number - 1) * 25 + 1
    end_index = min(start_index + 24, paginator.count)
    
    context = {
        'page': 'software_discovery',
        'page_obj': page_obj,
        'providers': providers,
        'search_query': search_query,
        'selected_provider': selected_provider,
        'search_name': search_name,
        'search_desc': search_desc,
        'search_topics': search_topics,
        'search_keywords': search_keywords,
        'error_message': error_message,
        'total_count': paginator.count,
        'start_index': start_index,
        'end_index': end_index,
    }
    return render(request, 'operations_portalcms_django/software_discovery.html', context)


@cache_page(60 * 15)  # Cache for 15 minutes
def software_detail(request, software_id):
    """Display detailed information for a specific software item"""
    api_url = 'https://operations-api.access-ci.org/wh2/glue2/v1/software_fast/?format=json'
    
    software_item = None
    error_message = None
    
    try:
        headers = {'Accept': 'application/json'}
        response = requests.get(api_url, headers=headers, timeout=30)
        response.raise_for_status()
        
        if not response.content:
            error_message = "API returned empty response"
        else:
            try:
                data = response.json()
                # Handle both list and dict responses
                if isinstance(data, list):
                    results = data
                else:
                    results = data.get('results', [])
                
                # Find the specific software item by ID
                for item in results:
                    if item.get('ID') == software_id:
                        software_item = item
                        break
                
                if not software_item:
                    error_message = "Software item not found"
                    
            except ValueError as json_err:
                error_message = f"Invalid JSON response: {str(json_err)}"
        
    except requests.RequestException as e:
        error_message = f"Unable to fetch software data: {str(e)}"
    
    context = {
        'page': 'software_detail',
        'software': software_item,
        'error_message': error_message,
    }
    return render(request, 'operations_portalcms_django/software_detail.html', context)


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
