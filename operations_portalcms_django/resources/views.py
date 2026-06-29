from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.shortcuts import render
from django.utils.cache import patch_cache_control
from django.views.decorators.cache import cache_page

from . import services


def render_resources_page(request, template_name, context):
    response = render(request, template_name, context)
    if context.get('error_message'):
        patch_cache_control(response, private=True, max_age=0)
    return response


@cache_page(60 * 15)
def access_allocated_resources(request):
    """Display ACCESS allocated resources."""
    resources_by_org, error_message = services.get_resource_listing('allocated')

    return render_resources_page(request, 'portal/access_allocated.html', {
        'page': 'access_allocated',
        'resources_by_org': resources_by_org,
        'error_message': error_message,
    })


@cache_page(60 * 15)
def access_online_services(request):
    """Display ACCESS online services."""
    resources_by_org, error_message = services.get_resource_listing('online_services')

    return render_resources_page(request, 'portal/access_online_services.html', {
        'page': 'access_online_services',
        'resources_by_org': resources_by_org,
        'error_message': error_message,
    })


@cache_page(60 * 15)
def software_discovery(request):
    """Display software catalog with search, filtering, and pagination."""

    search_query = request.GET.get('q', '').strip()
    selected_provider = request.GET.get('provider', '')
    search_name = request.GET.get('search_name', 'on') == 'on'
    search_desc = request.GET.get('search_desc', 'on') == 'on'
    search_topics = request.GET.get('search_topics', 'on') == 'on'
    search_keywords = request.GET.get('search_keywords', 'on') == 'on'

    software_list, providers, error_message = services.get_software_listing(
        search_query=search_query,
        selected_provider=selected_provider,
        search_name=search_name,
        search_desc=search_desc,
        search_topics=search_topics,
        search_keywords=search_keywords,
    )

    paginator = Paginator(software_list, 25)
    try:
        page_obj = paginator.get_page(request.GET.get('page', 1))
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    start_index = (page_obj.number - 1) * 25 + 1
    end_index = min(start_index + 24, paginator.count)

    return render_resources_page(request, 'portal/software_discovery.html', {
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
    """Display detailed information for a specific software item."""
    software_item, error_message = services.get_software_detail(software_id)

    return render_resources_page(request, 'portal/software_detail.html', {
        'page': 'software_detail',
        'software': software_item,
        'error_message': error_message,
    })


@cache_page(60 * 15)
def resource_detail(request, node_id):
    """Display detailed information for a single resource."""
    resource, error_message = services.get_resource_detail(node_id)

    return render_resources_page(request, 'portal/resource_detail.html', {
        'page': 'resource_detail',
        'resource': resource,
        'error_message': error_message,
    })
