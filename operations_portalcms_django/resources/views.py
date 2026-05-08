from django.shortcuts import render
from django.views.decorators.cache import cache_page
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
import requests
from collections import defaultdict


@cache_page(60 * 15)
def access_allocated_resources(request):
    """Display ACCESS allocated resources from API"""
    api_url = 'https://operations-api.access-ci.org/wh2/cider/v1/access-active/'
    resources_by_org = defaultdict(list)
    error_message = None

    try:
        response = requests.get(api_url, headers={'Accept': 'application/json'}, timeout=10)
        response.raise_for_status()
        if not response.content:
            error_message = 'API returned empty response'
            resources_by_org = {}
        else:
            try:
                data = response.json()
                for resource in data.get('results', []):
                    org_name = resource.get('organization_name', 'Unknown Organization') or 'Unknown Organization'
                    resources_by_org[org_name].append(resource)
                resources_by_org = dict(sorted(resources_by_org.items()))
            except ValueError as e:
                error_message = f'Invalid JSON response: {e}'
                resources_by_org = {}
    except requests.RequestException as e:
        error_message = f'Unable to fetch resources: {e}'
        resources_by_org = {}

    return render(request, 'portal/access_allocated.html', {
        'page': 'access_allocated',
        'resources_by_org': resources_by_org,
        'error_message': error_message,
    })


@cache_page(60 * 15)
def access_online_services(request):
    """Display ACCESS online services from API"""
    api_url = 'https://operations-api.access-ci.org/wh2/cider/v1/access-online-services/'
    resources_by_org = defaultdict(list)
    error_message = None

    try:
        response = requests.get(api_url, headers={'Accept': 'application/json'}, timeout=10)
        response.raise_for_status()
        if not response.content:
            error_message = 'API returned empty response'
            resources_by_org = {}
        else:
            try:
                data = response.json()
                for resource in data.get('results', []):
                    org_name = resource.get('organization_name', 'Unknown Organization') or 'Unknown Organization'
                    resources_by_org[org_name].append(resource)
                resources_by_org = dict(sorted(resources_by_org.items()))
            except ValueError as e:
                error_message = f'Invalid JSON response: {e}'
                resources_by_org = {}
    except requests.RequestException as e:
        error_message = f'Unable to fetch resources: {e}'
        resources_by_org = {}

    return render(request, 'portal/access_online_services.html', {
        'page': 'access_online_services',
        'resources_by_org': resources_by_org,
        'error_message': error_message,
    })


@cache_page(60 * 15)
def software_discovery(request):
    """Display software catalog from API with search, filtering, and pagination"""
    api_url = 'https://operations-api.access-ci.org/wh2/glue2/v1/software_fast/?format=json'
    software_list = []
    providers = {}
    error_message = None

    search_query = request.GET.get('q', '').strip()
    selected_provider = request.GET.get('provider', '')
    search_name = request.GET.get('search_name', 'on') == 'on'
    search_desc = request.GET.get('search_desc', 'on') == 'on'
    search_topics = request.GET.get('search_topics', 'on') == 'on'
    search_keywords = request.GET.get('search_keywords', 'on') == 'on'

    try:
        response = requests.get(api_url, headers={'Accept': 'application/json'}, timeout=30)
        response.raise_for_status()
        if not response.content:
            error_message = 'API returned empty response'
        else:
            try:
                data = response.json()
                results = data if isinstance(data, list) else data.get('results', [])

                provider_counts = defaultdict(int)
                for item in results:
                    provider_counts[item.get('ResourceID', 'Unknown Resource')] += 1
                providers = dict(sorted(provider_counts.items(), key=lambda x: x[1], reverse=True))

                if selected_provider:
                    results = [i for i in results if i.get('ResourceID', '') == selected_provider]

                if search_query:
                    q = search_query.lower()
                    filtered = []
                    for item in results:
                        match = (
                            (search_name and (
                                q in item.get('AppName', '').lower() or
                                q in item.get('AppVersion', '').lower() or
                                q in item.get('ResourceID', '').lower()
                            )) or
                            (search_desc and item.get('Description') and q in item['Description'].lower()) or
                            (search_topics and any(q in d.lower() for d in item.get('Domain', []))) or
                            (search_keywords and any(q in k.lower() for k in item.get('Keywords', []))) or
                            (search_desc and q in item.get('Handle', {}).get('HandleKey', '').lower())
                        )
                        if match:
                            filtered.append(item)
                    results = filtered

                software_list = results
            except ValueError as e:
                error_message = f'Invalid JSON response: {e}'
    except requests.RequestException as e:
        error_message = f'Unable to fetch software data: {e}'

    paginator = Paginator(software_list, 25)
    try:
        page_obj = paginator.get_page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    start_index = (page_obj.number - 1) * 25 + 1
    end_index = min(start_index + 24, paginator.count)

    return render(request, 'portal/software_discovery.html', {
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
    })


@cache_page(60 * 15)
def software_detail(request, software_id):
    """Display detailed information for a specific software item"""
    api_url = 'https://operations-api.access-ci.org/wh2/glue2/v1/software_fast/?format=json'
    software_item = None
    error_message = None

    try:
        response = requests.get(api_url, headers={'Accept': 'application/json'}, timeout=30)
        response.raise_for_status()
        if not response.content:
            error_message = 'API returned empty response'
        else:
            try:
                data = response.json()
                results = data if isinstance(data, list) else data.get('results', [])
                for item in results:
                    if item.get('ID') == software_id:
                        software_item = item
                        break
                if not software_item:
                    error_message = 'Software item not found'
            except ValueError as e:
                error_message = f'Invalid JSON response: {e}'
    except requests.RequestException as e:
        error_message = f'Unable to fetch software data: {e}'

    return render(request, 'portal/software_detail.html', {
        'page': 'software_detail',
        'software': software_item,
        'error_message': error_message,
    })


@cache_page(60 * 15)
def resource_detail(request, node_id):
    """Display detailed information for a single resource from CIDER API"""
    api_url = f'https://operations-api.access-ci.org/wh2/cider/v1/cider_resource_id/{node_id}/'
    resource = None
    error_message = None

    try:
        response = requests.get(api_url, headers={'Accept': 'application/json'}, timeout=10)
        response.raise_for_status()
        if not response.content:
            error_message = 'Resource not found'
        else:
            try:
                data = response.json()
                resource = data.get('results', {})
                if not resource:
                    error_message = 'Resource not found'
            except ValueError as e:
                error_message = f'Invalid JSON response: {e}'
    except requests.RequestException as e:
        error_message = f'Unable to fetch resource details: {e}'

    return render(request, 'portal/resource_detail.html', {
        'page': 'resource_detail',
        'resource': resource,
        'error_message': error_message,
    })
