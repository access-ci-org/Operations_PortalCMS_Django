from collections import Counter, defaultdict

import requests
from django.conf import settings
from django.db import DatabaseError

from .models import CiderInfrastructure


DEFAULT_OPERATIONS_API_BASE = "https://operations-api.access-ci.org/wh2"
DEFAULT_RESOURCE_TIMEOUT = 10
DEFAULT_SOFTWARE_TIMEOUT = 30
ONLINE_SERVICE_TYPE = "Online Service"


class ResourceDataError(Exception):
    """Raised when remote resource data cannot be fetched or parsed."""


def _settings_int(name, default):
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def operations_api_base():
    configured_base = (
        getattr(settings, "OPERATIONS_API_BASE", "")
        or getattr(settings, "API_BASE", "")
        or DEFAULT_OPERATIONS_API_BASE
    )
    return configured_base.rstrip("/")


def operations_api_url(path):
    return f"{operations_api_base()}/{path.lstrip('/')}"


def fetch_json(path, *, timeout, error_prefix):
    try:
        response = requests.get(
            operations_api_url(path),
            headers={"Accept": "application/json"},
            timeout=timeout,
        )
        response.raise_for_status()
    except requests.RequestException as e:
        raise ResourceDataError(f"{error_prefix}: {e}") from e

    if not response.content:
        raise ResourceDataError("API returned empty response")

    try:
        return response.json()
    except ValueError as e:
        raise ResourceDataError(f"Invalid JSON response: {e}") from e


def _resource_timeout():
    return _settings_int("OPERATIONS_RESOURCE_API_TIMEOUT", DEFAULT_RESOURCE_TIMEOUT)


def _software_timeout():
    return _settings_int("OPERATIONS_SOFTWARE_API_TIMEOUT", DEFAULT_SOFTWARE_TIMEOUT)


def _resource_to_dict(resource):
    other_attributes = resource.other_attributes if isinstance(resource.other_attributes, dict) else {}
    protected_attributes = resource.protected_attributes if isinstance(resource.protected_attributes, dict) else {}

    return {
        "cider_resource_id": resource.cider_resource_id,
        "cider_type": resource.cider_type,
        "info_resourceid": resource.info_resourceid,
        "info_siteid": resource.info_siteid,
        "resource_descriptive_name": resource.resource_descriptive_name,
        "resource_description": resource.resource_description,
        "resource_status": resource.resource_status,
        "current_statuses": resource.current_statuses,
        "latest_status": resource.latest_status,
        "latest_status_begin": resource.latest_status_begin,
        "latest_status_end": resource.latest_status_end,
        "recommended_use": resource.recommended_use,
        "access_description": resource.access_description,
        "project_affiliation": resource.project_affiliation,
        "provider_level": resource.provider_level,
        "organization_name": other_attributes.get("organization_name"),
        "organization_url": other_attributes.get("organization_url"),
        "organization_logo_url": other_attributes.get("organization_logo_url"),
        "cider_view_url": other_attributes.get("cider_view_url"),
        "cider_data_url": other_attributes.get("cider_data_url"),
        "short_name": other_attributes.get("short_name"),
        "features": protected_attributes.get("features") or other_attributes.get("features"),
        "user_guide_url": protected_attributes.get("user_guide_url") or other_attributes.get("user_guide_url"),
    }


def _group_resources_by_org(resources):
    resources_by_org = defaultdict(list)
    for resource in resources:
        org_name = resource.get("organization_name") or "Unknown Organization"
        resources_by_org[org_name].append(resource)
    return dict(sorted(resources_by_org.items()))


def _results_from_payload(data, label):
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        results = data.get("results", [])
        if isinstance(results, list):
            return results, None
    return [], f"Invalid JSON response: expected a list of {label}"


def _local_resource_dicts(kind):
    queryset = CiderInfrastructure.objects.all()
    if kind == "online_services":
        queryset = queryset.filter(cider_type__iexact=ONLINE_SERVICE_TYPE)
    else:
        queryset = queryset.exclude(cider_type__iexact=ONLINE_SERVICE_TYPE)
    queryset = queryset.order_by("resource_descriptive_name")
    return [_resource_to_dict(resource) for resource in queryset]


def _remote_resource_listing(kind):
    path = {
        "allocated": "/cider/v1/access-active/",
        "online_services": "/cider/v1/access-online-services/",
    }[kind]

    try:
        data = fetch_json(
            path,
            timeout=_resource_timeout(),
            error_prefix="Unable to fetch resources",
        )
    except ResourceDataError as e:
        return {}, str(e)

    results, error_message = _results_from_payload(data, "resources")
    if error_message:
        return {}, error_message
    return _group_resources_by_org(results), None


def get_resource_listing(kind):
    try:
        local_resources = _local_resource_dicts(kind)
    except DatabaseError:
        local_resources = []

    if local_resources:
        return _group_resources_by_org(local_resources), None

    return _remote_resource_listing(kind)


def get_resource_detail(node_id):
    try:
        resource = CiderInfrastructure.objects.get(cider_resource_id=node_id)
    except CiderInfrastructure.DoesNotExist:
        resource = None
    except DatabaseError:
        resource = None

    if resource is not None:
        return _resource_to_dict(resource), None

    try:
        data = fetch_json(
            f"/cider/v1/cider_resource_id/{node_id}/",
            timeout=_resource_timeout(),
            error_prefix="Unable to fetch resource details",
        )
    except ResourceDataError as e:
        return None, str(e)

    detail = data.get("results", {}) if isinstance(data, dict) else {}
    if not detail:
        return None, "Resource not found"
    return detail, None


def get_software_catalog():
    try:
        data = fetch_json(
            "/glue2/v1/software_fast/?format=json",
            timeout=_software_timeout(),
            error_prefix="Unable to fetch software data",
        )
    except ResourceDataError as e:
        return [], str(e)

    results, error_message = _results_from_payload(data, "software records")
    if error_message:
        return [], error_message
    return results, None


def get_software_listing(
    *,
    search_query="",
    selected_provider="",
    search_name=True,
    search_desc=True,
    search_topics=True,
    search_keywords=True,
):
    results, error_message = get_software_catalog()
    provider_counts = Counter(item.get("ResourceID") or "Unknown Resource" for item in results)
    providers = dict(provider_counts.most_common())

    if selected_provider:
        results = [item for item in results if item.get("ResourceID", "") == selected_provider]

    if search_query:
        q = search_query.lower()
        filtered = []
        for item in results:
            handle = item.get("Handle") or {}
            match = (
                (
                    search_name
                    and (
                        q in item.get("AppName", "").lower()
                        or q in item.get("AppVersion", "").lower()
                        or q in item.get("ResourceID", "").lower()
                    )
                )
                or (search_desc and item.get("Description") and q in item["Description"].lower())
                or (search_topics and any(q in domain.lower() for domain in item.get("Domain", [])))
                or (search_keywords and any(q in keyword.lower() for keyword in item.get("Keywords", [])))
                or (search_desc and q in handle.get("HandleKey", "").lower())
            )
            if match:
                filtered.append(item)
        results = filtered

    return results, providers, error_message


def get_software_detail(software_id):
    results, error_message = get_software_catalog()
    if error_message:
        return None, error_message

    for item in results:
        if item.get("ID") == software_id:
            return item, None

    return None, "Software item not found"
