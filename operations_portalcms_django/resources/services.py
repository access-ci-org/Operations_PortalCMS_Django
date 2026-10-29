"""Fetch and shape resource and software data for public portal views.

Public listings use the Operations API when available. The allocated-resource
listings can fall back to the last synchronized local CIDER projection during
an API outage; other resource views remain API-backed.
"""

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


# API configuration and transport


def _settings_int(name, default):
    try:
        return int(getattr(settings, name, default))
    except (TypeError, ValueError):
        return default


def operations_api_base():
    """Return the first configured API base URL, then the built-in fallback."""
    configured_base = (
        getattr(settings, "OPERATIONS_API_BASE", "")
        or getattr(settings, "API_BASE", "")
        or getattr(settings, "OPERATIONS_API_BASE_URL", "")
        or DEFAULT_OPERATIONS_API_BASE
    )
    return configured_base.rstrip("/")


def operations_api_url(path):
    """Build an Operations API URL from a relative path."""
    return f"{operations_api_base()}/{path.lstrip('/')}"


def fetch_json(path, *, timeout, error_prefix):
    """Fetch JSON and convert network, status, empty-body, and decode failures.

    Callers receive ResourceDataError with their supplied operation context
    instead of requests or JSON implementation details.
    """
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


# Resource normalization and filtering


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
        org_name = resource.get("organization_name")
        if not _has_value(org_name):
            continue
        org_name = str(org_name).strip()
        resources_by_org[org_name].append(resource)
    return dict(sorted(resources_by_org.items()))


def _has_value(value):
    return value is not None and str(value).strip() != ""


def _is_access_resource(resource):
    return str(resource.get("project_affiliation", "")).strip().upper() == "ACCESS"


def _publishable_resources(kind, resources):
    publishable = []
    for resource in resources:
        if not isinstance(resource, dict):
            continue
        if not _has_value(resource.get("organization_name")):
            continue
        if kind == "allocated":
            # v2/access-active/ includes online services too. Keep this
            # allocated listing aligned with its established Compute/Storage
            # scope, even if v2 later adds another resource type.
            resource_type = str(resource.get("cider_type", "")).strip().casefold()
            if resource_type not in {"compute", "storage"} or not _is_access_resource(resource):
                continue
        publishable.append(resource)
    return publishable


def _resource_kind(resource):
    cider_type = str(resource.get("cider_type", "")).strip()
    if cider_type.lower() == ONLINE_SERVICE_TYPE.lower():
        return "online_services"
    return "allocated"


def _is_publishable_resource(resource):
    if not _has_value(resource.get("organization_name")):
        return False
    return _resource_kind(resource) == "online_services" or _is_access_resource(resource)


def _results_from_payload(data, label):
    if isinstance(data, list):
        return data, None
    if isinstance(data, dict):
        results = data.get("results", [])
        if isinstance(results, list):
            return results, None
    return [], f"Invalid JSON response: expected a list of {label}"


def _local_resource_dicts(kind):
    queryset = CiderInfrastructure.objects.filter(is_active=True)
    if kind == "online_services":
        queryset = queryset.filter(cider_type__iexact=ONLINE_SERVICE_TYPE)
    else:
        queryset = queryset.exclude(cider_type__iexact=ONLINE_SERVICE_TYPE)
    queryset = queryset.order_by("resource_descriptive_name")
    return [_resource_to_dict(resource) for resource in queryset]


def _remote_resource_listing(kind):
    path = {
        "allocated": "/cider/v2/access-active/",
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
    publishable = _publishable_resources(kind, results)
    if kind == "allocated" and not publishable:
        return {}, "CIDER returned no allocated resources."
    return _group_resources_by_org(publishable), None


# Public resource queries


def get_resource_listing(kind):
    """Return public resource listing grouped by organisation.

    The Warehouse API is authoritative. If the allocated-resource endpoint is
    unavailable, use the last synchronized active Compute/Storage projection
    as a fallback. Online services and other listings remain API-only.
    """
    resources_by_org, error_message = _remote_resource_listing(kind)
    if error_message is None or kind != "allocated":
        return resources_by_org, error_message

    try:
        local_resources = _local_resource_dicts("allocated")
    except DatabaseError:
        return resources_by_org, error_message

    fallback_resources = _publishable_resources("allocated", local_resources)
    fallback_by_org = _group_resources_by_org(fallback_resources)
    if not fallback_by_org:
        return resources_by_org, error_message

    return fallback_by_org, "CIDER is temporarily unavailable; showing the last synchronized resource data."


def get_active_infrastructure_queryset():
    """Return the queryset of active local CIDER infrastructure rows.

    Intended for news entry forms and admin selectors. Public resource pages
    use the Warehouse API first, with a limited allocated-resource fallback.
    """
    return CiderInfrastructure.objects.filter(is_active=True).order_by("resource_descriptive_name")


def get_resource_detail(node_id):
    """Return a single publishable resource dict from the Warehouse API.

    Data comes exclusively from the Warehouse API. An unavailable API returns
    an error message rather than silently serving stale local projection data.
    """
    try:
        data = fetch_json(
            f"/cider/v1/cider_resource_id/{node_id}/",
            timeout=_resource_timeout(),
            error_prefix="Unable to fetch resource details",
        )
    except ResourceDataError as e:
        return None, str(e)

    detail = data.get("results", {}) if isinstance(data, dict) else {}
    if not isinstance(detail, dict):
        detail = {}
    if not detail or not _is_publishable_resource(detail):
        return None, "Resource not found"
    return detail, None


# Public software catalog queries


def get_software_catalog():
    """Return ``(catalog_records, error_message)`` from the software API."""
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
    """Return filtered records, unfiltered provider counts, and any API error.

    Provider counts are calculated before provider and text filters so the UI
    can continue to display every available provider option.
    """
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
    """Return ``(record, error_message)`` for one software ID."""
    results, error_message = get_software_catalog()
    if error_message:
        return None, error_message

    for item in results:
        if item.get("ID") == software_id:
            return item, None

    return None, "Software item not found"
