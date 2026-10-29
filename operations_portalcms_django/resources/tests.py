from unittest.mock import Mock, patch

import requests
from django.core.management.base import CommandError
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from . import services, views
from .management.commands.sync_cider_from_api import Command as SyncCiderCommand


class MockResponse:
    def __init__(self, *, content=b"{}", payload=None, json_error=None, http_error=None):
        self.content = content
        self.payload = payload if payload is not None else {}
        self.json_error = json_error
        self.http_error = http_error

    def raise_for_status(self):
        if self.http_error:
            raise self.http_error

    def json(self):
        if self.json_error:
            raise self.json_error
        return self.payload


def fake_render(request, template_name, context):
    response = HttpResponse("")
    response.template_name = template_name
    response.context_data = context
    return response


class ResourceServiceTests(SimpleTestCase):
    @patch("resources.services.requests.get")
    def test_remote_resource_listing_groups_by_organization(self, mock_get):
        mock_get.return_value = MockResponse(
            payload={
                "results": [
                    {
                        "cider_type": "Compute",
                        "resource_descriptive_name": "Beta",
                        "organization_name": "Org B",
                        "project_affiliation": "ACCESS",
                    },
                    {
                        "cider_type": "Compute",
                        "resource_descriptive_name": "Alpha",
                        "organization_name": "Org A",
                        "project_affiliation": "ACCESS",
                    },
                ],
            }
        )

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertIsNone(error_message)
        self.assertEqual(list(resources_by_org), ["Org A", "Org B"])
        self.assertEqual(resources_by_org["Org A"][0]["resource_descriptive_name"], "Alpha")
        mock_get.assert_called_once()

    @patch("resources.services._local_resource_dicts", return_value=[])
    @patch("resources.services.requests.get")
    def test_empty_resource_api_response_returns_error(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(content=b"")

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertEqual(resources_by_org, {})
        self.assertEqual(error_message, "API returned empty response")

    @patch("resources.services._local_resource_dicts", return_value=[])
    @patch("resources.services.requests.get")
    def test_upstream_resource_error_returns_error_when_cache_is_empty(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(http_error=requests.HTTPError("503"))

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertEqual(resources_by_org, {})
        self.assertIn("Unable to fetch resources", error_message)
        self.assertIn("503", error_message)

    @patch("resources.services._local_resource_dicts")
    @patch("resources.services.requests.get")
    def test_allocated_api_failure_uses_local_active_resource_fallback(self, mock_get, mock_local):
        mock_get.return_value = MockResponse(http_error=requests.HTTPError("503"))
        mock_local.return_value = [
            {
                "cider_type": "Compute",
                "resource_descriptive_name": "Cached Compute",
                "organization_name": "Cached Org",
                "project_affiliation": "ACCESS",
            },
            {
                "cider_type": "Storage",
                "resource_descriptive_name": "Cached Storage",
                "organization_name": "Cached Org",
                "project_affiliation": "ACCESS",
            },
        ]

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertEqual(
            [resource["resource_descriptive_name"] for resource in resources_by_org["Cached Org"]],
            ["Cached Compute", "Cached Storage"],
        )
        self.assertIn("last synchronized", error_message)
        mock_local.assert_called_once_with("allocated")
        mock_get.assert_called_once()

    @patch("resources.services._local_resource_dicts")
    @patch("resources.services.requests.get")
    def test_online_services_api_failure_does_not_use_allocated_fallback(self, mock_get, mock_local):
        mock_get.return_value = MockResponse(http_error=requests.HTTPError("503"))

        resources_by_org, error_message = services.get_resource_listing("online_services")

        self.assertEqual(resources_by_org, {})
        self.assertIn("Unable to fetch resources", error_message)
        mock_local.assert_not_called()

    @patch("resources.services._local_resource_dicts")
    @patch("resources.services.requests.get")
    def test_empty_allocated_response_uses_local_fallback(self, mock_get, mock_local):
        mock_get.return_value = MockResponse(payload={"results": []})
        mock_local.return_value = [
            {
                "cider_type": "Compute",
                "resource_descriptive_name": "Cached Compute",
                "organization_name": "Cached Org",
                "project_affiliation": "ACCESS",
            }
        ]

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertEqual(resources_by_org["Cached Org"][0]["resource_descriptive_name"], "Cached Compute")
        self.assertIn("no allocated resources", error_message)
        mock_local.assert_called_once_with("allocated")

    @patch("resources.services.CiderInfrastructure.objects.filter")
    def test_local_allocated_query_excludes_inactive_and_online_services(self, mock_filter):
        queryset = Mock()
        queryset.exclude.return_value = queryset
        queryset.order_by.return_value = []
        mock_filter.return_value = queryset

        self.assertEqual(services._local_resource_dicts("allocated"), [])

        mock_filter.assert_called_once_with(is_active=True)
        queryset.exclude.assert_called_once_with(cider_type__iexact="Online Service")
        queryset.order_by.assert_called_once_with("resource_descriptive_name")

    @patch("resources.services._local_resource_dicts", return_value=[])
    @patch("resources.services.requests.get")
    def test_invalid_resource_json_returns_error(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(json_error=ValueError("bad json"))

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertEqual(resources_by_org, {})
        self.assertIn("Invalid JSON response", error_message)

    @patch("resources.services.requests.get")
    def test_remote_allocated_listing_filters_noncanonical_rows(self, mock_get):
        mock_get.return_value = MockResponse(
            payload={
                "results": [
                    {
                        "cider_type": "Compute",
                        "resource_descriptive_name": "Canonical",
                        "organization_name": "Known Org",
                        "project_affiliation": "ACCESS",
                    },
                    {
                        "cider_type": "Compute",
                        "resource_descriptive_name": "Missing Org",
                        "organization_name": "",
                        "project_affiliation": "ACCESS",
                    },
                    {
                        "cider_type": "Compute",
                        "resource_descriptive_name": "Non ACCESS",
                        "organization_name": "Known Org",
                        "project_affiliation": "",
                    },
                ],
            }
        )

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertIsNone(error_message)
        self.assertEqual([item["resource_descriptive_name"] for item in resources_by_org["Known Org"]], ["Canonical"])
        self.assertNotIn("Unknown Organization", resources_by_org)

    @patch("resources.services.requests.get")
    def test_v2_allocated_listing_excludes_online_services(self, mock_get):
        mock_get.return_value = MockResponse(
            payload={
                "results": [
                    {
                        "cider_type": "Compute",
                        "resource_descriptive_name": "Allocated Compute",
                        "organization_name": "ACCESS Org",
                        "project_affiliation": "ACCESS",
                    },
                    {
                        "cider_type": "Online Service",
                        "resource_descriptive_name": "Online Service",
                        "organization_name": "ACCESS Org",
                        "project_affiliation": "ACCESS",
                    },
                    {
                        "cider_type": "Future Type",
                        "resource_descriptive_name": "Unrecognized Type",
                        "organization_name": "ACCESS Org",
                        "project_affiliation": "ACCESS",
                    },
                ],
            }
        )

        resources_by_org, error_message = services.get_resource_listing("allocated")

        self.assertIsNone(error_message)
        self.assertEqual(
            [item["resource_descriptive_name"] for item in resources_by_org["ACCESS Org"]],
            ["Allocated Compute"],
        )
        self.assertTrue(mock_get.call_args.args[0].endswith("/cider/v2/access-active/"))

    @patch("resources.services.requests.get")
    def test_remote_online_services_require_org_but_not_access_project(self, mock_get):
        mock_get.return_value = MockResponse(
            payload={
                "results": [
                    {
                        "resource_descriptive_name": "Online Service",
                        "organization_name": "Service Org",
                        "project_affiliation": "",
                    },
                    {
                        "resource_descriptive_name": "Missing Org Service",
                        "organization_name": "",
                        "project_affiliation": "",
                    },
                ],
            }
        )

        resources_by_org, error_message = services.get_resource_listing("online_services")

        self.assertIsNone(error_message)
        self.assertEqual(
            [item["resource_descriptive_name"] for item in resources_by_org["Service Org"]],
            ["Online Service"],
        )
        self.assertNotIn("Unknown Organization", resources_by_org)

    @patch("resources.services.get_software_catalog")
    def test_software_listing_filters_and_counts_providers(self, mock_catalog):
        mock_catalog.return_value = (
            [
                {
                    "ID": "numpy-anvil",
                    "AppName": "NumPy",
                    "AppVersion": "2.0",
                    "ResourceID": "anvil",
                    "Description": "Python arrays",
                    "Domain": ["Math"],
                    "Keywords": ["python"],
                    "Handle": {"HandleKey": "numpy"},
                },
                {
                    "ID": "blast-bridges",
                    "AppName": "BLAST",
                    "AppVersion": "1.0",
                    "ResourceID": "bridges2",
                    "Description": "Sequence search",
                    "Domain": ["Biology"],
                    "Keywords": ["genomics"],
                    "Handle": {"HandleKey": "blast"},
                },
            ],
            None,
        )

        software, providers, error_message = services.get_software_listing(
            search_query="numpy",
            selected_provider="anvil",
        )

        self.assertIsNone(error_message)
        self.assertEqual([item["ID"] for item in software], ["numpy-anvil"])
        self.assertEqual(providers, {"anvil": 1, "bridges2": 1})

    @patch("resources.services.get_software_catalog")
    def test_missing_software_detail_returns_not_found(self, mock_catalog):
        mock_catalog.return_value = ([{"ID": "numpy-anvil", "AppName": "NumPy"}], None)

        software, error_message = services.get_software_detail("missing-id")

        self.assertIsNone(software)
        self.assertEqual(error_message, "Software item not found")

    @patch("resources.services.fetch_json", return_value={"results": {}})
    def test_missing_resource_detail_returns_not_found(self, _mock_fetch):
        resource, error_message = services.get_resource_detail(404)

        self.assertIsNone(resource)
        self.assertEqual(error_message, "Resource not found")

    @patch("resources.services.fetch_json")
    def test_resource_detail_api_failure_returns_error(self, mock_fetch):
        """An unavailable detail API must return an error, not silently serve local rows."""
        mock_fetch.side_effect = services.ResourceDataError("Unable to fetch resource details: 503")

        resource, error_message = services.get_resource_detail(101)

        self.assertIsNone(resource)
        self.assertIn("Unable to fetch resource details", error_message)

    @patch("resources.services.fetch_json")
    def test_unpublishable_remote_resource_detail_returns_not_found(self, mock_fetch):
        mock_fetch.return_value = {
            "results": {
                "resource_descriptive_name": "Remote Orphan",
                "organization_name": "",
                "project_affiliation": "",
            },
        }

        resource, error_message = services.get_resource_detail(103)

        self.assertIsNone(resource)
        self.assertEqual(error_message, "Resource not found")

    @patch("resources.services.fetch_json")
    def test_resource_detail_keeps_access_types_outside_allocated_listing_filter(self, mock_fetch):
        mock_fetch.return_value = {
            "results": {
                "cider_type": "Future Type",
                "resource_descriptive_name": "Other ACCESS Resource",
                "organization_name": "ACCESS Org",
                "project_affiliation": "ACCESS",
            },
        }

        resource, error_message = services.get_resource_detail(104)

        self.assertIsNone(error_message)
        self.assertEqual(resource["resource_descriptive_name"], "Other ACCESS Resource")


class CiderSyncValidationTests(SimpleTestCase):
    def setUp(self):
        self.command = SyncCiderCommand()

    def test_infrastructure_payload_must_be_complete_and_have_unique_ids(self):
        valid = {"results": [{"cider_resource_id": 10}, {"cider_resource_id": 11}]}
        self.assertEqual(self.command.validate_infrastructure_payload(valid), valid["results"])

        invalid_payloads = (
            {},
            {"results": []},
            {"results": [{"cider_resource_id": None}]},
            {"results": [{"cider_resource_id": 10}, {"cider_resource_id": 10}]},
            {"results": ["not a resource object"]},
        )
        for payload in invalid_payloads:
            with self.subTest(payload=payload), self.assertRaises(CommandError):
                self.command.validate_infrastructure_payload(payload)

    def test_groups_payload_requires_expected_collections(self):
        valid = {
            "results": {
                "active_groups": [],
                "organizations": [],
                "feature_categories": [],
                "features": [],
            }
        }
        self.command.validate_groups_payload(valid)

        with self.assertRaises(CommandError):
            self.command.validate_groups_payload({"results": {"active_groups": []}})

    @patch("resources.management.commands.sync_cider_from_api.requests.get")
    def test_api_request_failure_raises_command_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("offline")
        options = {
            "api_url": "https://example.invalid",
            "timeout": 1,
            "group_prefix": "",
            "dry_run": False,
            "skip_infrastructure": False,
            "skip_groups_bundle": True,
            "prune_stale_groups": False,
        }

        with self.assertRaisesRegex(CommandError, "CIDER API request failed"):
            self.command.handle(**options)


class ResourceViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch("resources.views.render", side_effect=fake_render)
    @patch("resources.views.services.get_resource_listing")
    def test_access_allocated_view_uses_service_context(self, mock_listing, _mock_render):
        mock_listing.return_value = ({"Org": [{"resource_descriptive_name": "Alpha"}]}, None)

        response = views.access_allocated_resources.__wrapped__(self.factory.get("/resources/access-allocated/"))

        self.assertEqual(response.template_name, "portal/access_allocated.html")
        self.assertEqual(response.context_data["page"], "access_allocated")
        self.assertEqual(response.context_data["resources_by_org"]["Org"][0]["resource_descriptive_name"], "Alpha")
        self.assertIsNone(response.context_data["error_message"])

    @patch("resources.views.render", side_effect=fake_render)
    @patch("resources.views.services.get_resource_listing")
    def test_infrastructure_view_renders_fallback_resources_with_warning(self, mock_listing, _mock_render):
        mock_listing.return_value = (
            {"Org": [{"resource_descriptive_name": "Cached Compute"}]},
            "CIDER is temporarily unavailable; showing the last synchronized resource data.",
        )

        response = views.infrastructure.__wrapped__(self.factory.get("/infrastructure"))

        self.assertEqual(response.template_name, "portal/infrastructure_list.html")
        self.assertEqual(response.context_data["page_obj"].object_list[0]["resource_descriptive_name"], "Cached Compute")
        self.assertIn("last synchronized", response.context_data["error_message"])

    @patch("resources.views.render", side_effect=fake_render)
    @patch("resources.views.services.get_resource_listing")
    def test_error_view_response_is_not_publicly_cacheable(self, mock_listing, _mock_render):
        mock_listing.return_value = ({}, "Unable to fetch resources: 503")

        response = views.access_allocated_resources.__wrapped__(self.factory.get("/resources/access-allocated/"))

        self.assertIn("private", response.headers["Cache-Control"])
        self.assertIn("max-age=0", response.headers["Cache-Control"])

    @patch("resources.views.render", side_effect=fake_render)
    @patch("resources.views.services.get_software_listing")
    def test_software_discovery_paginates_service_results(self, mock_listing, _mock_render):
        mock_listing.return_value = (
            [{"ID": f"app-{index}", "AppName": f"App {index}"} for index in range(30)],
            {"anvil": 30},
            None,
        )

        response = views.software_discovery.__wrapped__(self.factory.get("/software_discovery/?q=app"))

        self.assertEqual(response.template_name, "portal/software_discovery.html")
        self.assertEqual(response.context_data["total_count"], 30)
        self.assertEqual(response.context_data["start_index"], 1)
        self.assertEqual(response.context_data["end_index"], 25)
        self.assertEqual(len(response.context_data["page_obj"].object_list), 25)
        mock_listing.assert_called_once_with(
            search_query="app",
            selected_provider="",
            search_name=True,
            search_desc=True,
            search_topics=True,
            search_keywords=True,
        )

    @patch("resources.views.render", side_effect=fake_render)
    @patch("resources.views.services.get_software_detail")
    def test_software_detail_view_reports_missing_item(self, mock_detail, _mock_render):
        mock_detail.return_value = (None, "Software item not found")

        response = views.software_detail.__wrapped__(self.factory.get("/resources/software/missing/"), "missing")

        self.assertIsNone(response.context_data["software"])
        self.assertEqual(response.context_data["error_message"], "Software item not found")
        self.assertIn("private", response.headers["Cache-Control"])

    @patch("resources.views.render", side_effect=fake_render)
    @patch("resources.views.services.get_resource_detail")
    def test_resource_detail_view_uses_service_context(self, mock_detail, _mock_render):
        mock_detail.return_value = ({"resource_descriptive_name": "Alpha"}, None)

        response = views.resource_detail.__wrapped__(self.factory.get("/node/1/"), 1)

        self.assertEqual(response.template_name, "portal/resource_detail.html")
        self.assertEqual(response.context_data["resource"]["resource_descriptive_name"], "Alpha")
        self.assertIsNone(response.context_data["error_message"])
