from types import SimpleNamespace
from unittest.mock import patch

import requests
from django.http import HttpResponse
from django.test import RequestFactory, SimpleTestCase

from . import services, views


class MockResponse:
    def __init__(self, *, content=b'{}', payload=None, json_error=None, http_error=None):
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
    response = HttpResponse('')
    response.template_name = template_name
    response.context_data = context
    return response


def fake_cider_resource(**overrides):
    defaults = {
        'cider_resource_id': 1,
        'cider_type': 'Compute',
        'info_resourceid': '',
        'info_siteid': '',
        'resource_descriptive_name': 'Cached Resource',
        'resource_description': '',
        'resource_status': 'active',
        'current_statuses': [],
        'latest_status': '',
        'latest_status_begin': None,
        'latest_status_end': None,
        'recommended_use': '',
        'access_description': '',
        'project_affiliation': 'ACCESS',
        'provider_level': '',
        'other_attributes': {'organization_name': 'Local Org'},
        'protected_attributes': {},
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class ResourceServiceTests(SimpleTestCase):
    @patch('resources.services._local_resource_dicts', return_value=[])
    @patch('resources.services.requests.get')
    def test_remote_resource_listing_groups_by_organization(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(payload={
            'results': [
                {
                    'resource_descriptive_name': 'Beta',
                    'organization_name': 'Org B',
                    'project_affiliation': 'ACCESS',
                },
                {
                    'resource_descriptive_name': 'Alpha',
                    'organization_name': 'Org A',
                    'project_affiliation': 'ACCESS',
                },
            ],
        })

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertIsNone(error_message)
        self.assertEqual(list(resources_by_org), ['Org A', 'Org B'])
        self.assertEqual(resources_by_org['Org A'][0]['resource_descriptive_name'], 'Alpha')
        mock_get.assert_called_once()

    @patch('resources.services._local_resource_dicts', return_value=[])
    @patch('resources.services.requests.get')
    def test_empty_resource_api_response_returns_error(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(content=b'')

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertEqual(resources_by_org, {})
        self.assertEqual(error_message, 'API returned empty response')

    @patch('resources.services._local_resource_dicts', return_value=[])
    @patch('resources.services.requests.get')
    def test_upstream_resource_error_returns_error(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(http_error=requests.HTTPError('503'))

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertEqual(resources_by_org, {})
        self.assertIn('Unable to fetch resources', error_message)
        self.assertIn('503', error_message)

    @patch('resources.services._local_resource_dicts', return_value=[])
    @patch('resources.services.requests.get')
    def test_invalid_resource_json_returns_error(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(json_error=ValueError('bad json'))

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertEqual(resources_by_org, {})
        self.assertIn('Invalid JSON response', error_message)

    @patch('resources.services._local_resource_dicts', return_value=[])
    @patch('resources.services.requests.get')
    def test_remote_allocated_listing_filters_noncanonical_rows(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(payload={
            'results': [
                {
                    'resource_descriptive_name': 'Canonical',
                    'organization_name': 'Known Org',
                    'project_affiliation': 'ACCESS',
                },
                {
                    'resource_descriptive_name': 'Missing Org',
                    'organization_name': '',
                    'project_affiliation': 'ACCESS',
                },
                {
                    'resource_descriptive_name': 'Non ACCESS',
                    'organization_name': 'Known Org',
                    'project_affiliation': '',
                },
            ],
        })

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertIsNone(error_message)
        self.assertEqual([item['resource_descriptive_name'] for item in resources_by_org['Known Org']], ['Canonical'])
        self.assertNotIn('Unknown Organization', resources_by_org)

    @patch('resources.services._local_resource_dicts', return_value=[])
    @patch('resources.services.requests.get')
    def test_remote_online_services_require_org_but_not_access_project(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(payload={
            'results': [
                {
                    'resource_descriptive_name': 'Online Service',
                    'organization_name': 'Service Org',
                    'project_affiliation': '',
                },
                {
                    'resource_descriptive_name': 'Missing Org Service',
                    'organization_name': '',
                    'project_affiliation': '',
                },
            ],
        })

        resources_by_org, error_message = services.get_resource_listing('online_services')

        self.assertIsNone(error_message)
        self.assertEqual(
            [item['resource_descriptive_name'] for item in resources_by_org['Service Org']],
            ['Online Service'],
        )
        self.assertNotIn('Unknown Organization', resources_by_org)

    @patch('resources.services._local_resource_dicts')
    @patch('resources.services.requests.get')
    def test_local_resource_cache_prevents_remote_fetch(self, mock_get, mock_local):
        mock_local.return_value = [{
            'resource_descriptive_name': 'Cached',
            'organization_name': 'Local Org',
            'project_affiliation': 'ACCESS',
        }]

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertIsNone(error_message)
        self.assertEqual(resources_by_org['Local Org'][0]['resource_descriptive_name'], 'Cached')
        mock_get.assert_not_called()

    @patch('resources.services._local_resource_dicts')
    @patch('resources.services.requests.get')
    def test_local_allocated_listing_filters_noncanonical_rows(self, mock_get, mock_local):
        mock_local.return_value = [
            {
                'resource_descriptive_name': 'Canonical',
                'organization_name': 'Known Org',
                'project_affiliation': 'ACCESS',
            },
            {
                'resource_descriptive_name': 'Missing Org',
                'organization_name': '',
                'project_affiliation': 'ACCESS',
            },
            {
                'resource_descriptive_name': 'Non ACCESS',
                'organization_name': 'Known Org',
                'project_affiliation': '',
            },
        ]

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertIsNone(error_message)
        self.assertEqual([item['resource_descriptive_name'] for item in resources_by_org['Known Org']], ['Canonical'])
        self.assertNotIn('Unknown Organization', resources_by_org)
        mock_get.assert_not_called()

    @patch('resources.services._local_resource_dicts', return_value=[{
        'resource_descriptive_name': 'Orphan',
        'organization_name': '',
        'project_affiliation': '',
    }])
    @patch('resources.services.requests.get')
    def test_local_orphans_do_not_block_remote_resource_fallback(self, mock_get, _mock_local):
        mock_get.return_value = MockResponse(payload={
            'results': [{
                'resource_descriptive_name': 'Remote Canonical',
                'organization_name': 'Remote Org',
                'project_affiliation': 'ACCESS',
            }],
        })

        resources_by_org, error_message = services.get_resource_listing('allocated')

        self.assertIsNone(error_message)
        self.assertEqual(resources_by_org['Remote Org'][0]['resource_descriptive_name'], 'Remote Canonical')
        self.assertNotIn('Unknown Organization', resources_by_org)
        mock_get.assert_called_once()

    @patch('resources.services.get_software_catalog')
    def test_software_listing_filters_and_counts_providers(self, mock_catalog):
        mock_catalog.return_value = ([
            {
                'ID': 'numpy-anvil',
                'AppName': 'NumPy',
                'AppVersion': '2.0',
                'ResourceID': 'anvil',
                'Description': 'Python arrays',
                'Domain': ['Math'],
                'Keywords': ['python'],
                'Handle': {'HandleKey': 'numpy'},
            },
            {
                'ID': 'blast-bridges',
                'AppName': 'BLAST',
                'AppVersion': '1.0',
                'ResourceID': 'bridges2',
                'Description': 'Sequence search',
                'Domain': ['Biology'],
                'Keywords': ['genomics'],
                'Handle': {'HandleKey': 'blast'},
            },
        ], None)

        software, providers, error_message = services.get_software_listing(
            search_query='numpy',
            selected_provider='anvil',
        )

        self.assertIsNone(error_message)
        self.assertEqual([item['ID'] for item in software], ['numpy-anvil'])
        self.assertEqual(providers, {'anvil': 1, 'bridges2': 1})

    @patch('resources.services.get_software_catalog')
    def test_missing_software_detail_returns_not_found(self, mock_catalog):
        mock_catalog.return_value = ([{'ID': 'numpy-anvil', 'AppName': 'NumPy'}], None)

        software, error_message = services.get_software_detail('missing-id')

        self.assertIsNone(software)
        self.assertEqual(error_message, 'Software item not found')

    @patch('resources.services.fetch_json', return_value={'results': {}})
    @patch.object(services.CiderInfrastructure.objects, 'get')
    def test_missing_resource_detail_returns_not_found(self, mock_get, _mock_fetch):
        mock_get.side_effect = services.CiderInfrastructure.DoesNotExist

        resource, error_message = services.get_resource_detail(404)

        self.assertIsNone(resource)
        self.assertEqual(error_message, 'Resource not found')

    @patch('resources.services.fetch_json')
    @patch.object(services.CiderInfrastructure.objects, 'get')
    def test_publishable_local_resource_detail_prevents_remote_fetch(self, mock_get, mock_fetch):
        mock_get.return_value = fake_cider_resource(
            resource_descriptive_name='Canonical Cached',
            other_attributes={'organization_name': 'Known Org'},
            project_affiliation='ACCESS',
        )

        resource, error_message = services.get_resource_detail(101)

        self.assertIsNone(error_message)
        self.assertEqual(resource['resource_descriptive_name'], 'Canonical Cached')
        mock_fetch.assert_not_called()

    @patch('resources.services.fetch_json')
    @patch.object(services.CiderInfrastructure.objects, 'get')
    def test_unpublishable_local_resource_detail_falls_back_to_remote(self, mock_get, mock_fetch):
        mock_get.return_value = fake_cider_resource(
            resource_descriptive_name='Local Orphan',
            other_attributes={'organization_name': ''},
            project_affiliation='',
        )
        mock_fetch.return_value = {
            'results': {
                'resource_descriptive_name': 'Remote Canonical',
                'organization_name': 'Remote Org',
                'project_affiliation': 'ACCESS',
            },
        }

        resource, error_message = services.get_resource_detail(102)

        self.assertIsNone(error_message)
        self.assertEqual(resource['resource_descriptive_name'], 'Remote Canonical')
        mock_fetch.assert_called_once()

    @patch('resources.services.fetch_json')
    @patch.object(services.CiderInfrastructure.objects, 'get')
    def test_unpublishable_remote_resource_detail_returns_not_found(self, mock_get, mock_fetch):
        mock_get.side_effect = services.CiderInfrastructure.DoesNotExist
        mock_fetch.return_value = {
            'results': {
                'resource_descriptive_name': 'Remote Orphan',
                'organization_name': '',
                'project_affiliation': '',
            },
        }

        resource, error_message = services.get_resource_detail(103)

        self.assertIsNone(resource)
        self.assertEqual(error_message, 'Resource not found')


class ResourceViewTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    @patch('resources.views.render', side_effect=fake_render)
    @patch('resources.views.services.get_resource_listing')
    def test_access_allocated_view_uses_service_context(self, mock_listing, _mock_render):
        mock_listing.return_value = ({'Org': [{'resource_descriptive_name': 'Alpha'}]}, None)

        response = views.access_allocated_resources.__wrapped__(self.factory.get('/resources/access-allocated/'))

        self.assertEqual(response.template_name, 'portal/access_allocated.html')
        self.assertEqual(response.context_data['page'], 'access_allocated')
        self.assertEqual(response.context_data['resources_by_org']['Org'][0]['resource_descriptive_name'], 'Alpha')
        self.assertIsNone(response.context_data['error_message'])

    @patch('resources.views.render', side_effect=fake_render)
    @patch('resources.views.services.get_resource_listing')
    def test_error_view_response_is_not_publicly_cacheable(self, mock_listing, _mock_render):
        mock_listing.return_value = ({}, 'Unable to fetch resources: 503')

        response = views.access_allocated_resources.__wrapped__(self.factory.get('/resources/access-allocated/'))

        self.assertIn('private', response.headers['Cache-Control'])
        self.assertIn('max-age=0', response.headers['Cache-Control'])

    @patch('resources.views.render', side_effect=fake_render)
    @patch('resources.views.services.get_software_listing')
    def test_software_discovery_paginates_service_results(self, mock_listing, _mock_render):
        mock_listing.return_value = (
            [{'ID': f'app-{index}', 'AppName': f'App {index}'} for index in range(30)],
            {'anvil': 30},
            None,
        )

        response = views.software_discovery.__wrapped__(self.factory.get('/resources/software-discovery/?q=app'))

        self.assertEqual(response.template_name, 'portal/software_discovery.html')
        self.assertEqual(response.context_data['total_count'], 30)
        self.assertEqual(response.context_data['start_index'], 1)
        self.assertEqual(response.context_data['end_index'], 25)
        self.assertEqual(len(response.context_data['page_obj'].object_list), 25)
        mock_listing.assert_called_once_with(
            search_query='app',
            selected_provider='',
            search_name=True,
            search_desc=True,
            search_topics=True,
            search_keywords=True,
        )

    @patch('resources.views.render', side_effect=fake_render)
    @patch('resources.views.services.get_software_detail')
    def test_software_detail_view_reports_missing_item(self, mock_detail, _mock_render):
        mock_detail.return_value = (None, 'Software item not found')

        response = views.software_detail.__wrapped__(self.factory.get('/resources/software/missing/'), 'missing')

        self.assertIsNone(response.context_data['software'])
        self.assertEqual(response.context_data['error_message'], 'Software item not found')
        self.assertIn('private', response.headers['Cache-Control'])

    @patch('resources.views.render', side_effect=fake_render)
    @patch('resources.views.services.get_resource_detail')
    def test_resource_detail_view_uses_service_context(self, mock_detail, _mock_render):
        mock_detail.return_value = ({'resource_descriptive_name': 'Alpha'}, None)

        response = views.resource_detail.__wrapped__(self.factory.get('/node/1/'), 1)

        self.assertEqual(response.template_name, 'portal/resource_detail.html')
        self.assertEqual(response.context_data['resource']['resource_descriptive_name'], 'Alpha')
        self.assertIsNone(response.context_data['error_message'])
