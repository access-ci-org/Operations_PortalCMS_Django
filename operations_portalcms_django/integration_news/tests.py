import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from . import workflow
from .models import IntegrationElement, IntegrationNews


class AuthenticatedReviewer:
    is_authenticated = True
    is_active = True
    is_superuser = True

    def has_perm(self, _perm):
        return True

    def has_perms(self, _perms):
        return True


class IntegrationWorkflowMethodTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_workflow_state_changes_reject_get_requests(self):
        views = [
            workflow.submit_integration_for_review,
            workflow.approve_integration_news,
            workflow.reject_integration_news,
            workflow.publish_integration_news,
            workflow.unpublish_integration_news,
        ]

        for view in views:
            with self.subTest(view=view.__name__):
                request = self.factory.get('/integration-news/1/state/')
                request.user = AuthenticatedReviewer()

                response = view(request, pk=1)

                self.assertEqual(response.status_code, 405)


class IntegrationNewsAuthorDisplayTests(TestCase):
    def test_anonymous_page_shows_published_author_name_without_email(self):
        author = User.objects.create_user(
            username='integration_test_author',
            first_name='Integration Test',
            last_name='Author',
            email='private-integration-author@example.test',
        )
        IntegrationNews.objects.create(
            title='Published integration item',
            content='Published integration content',
            news_type='software_release',
            author=author,
            status='published',
            is_active=True,
        )

        response = self.client.get('/integration-news/')

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Author: Integration Test Author')
        self.assertNotContains(response, author.email)


class ApiIntegrationNewsTests(TestCase):
    def setUp(self):
        # @cache_page on the view caches the full response process-wide, independent
        # of each test's transaction rollback, so a prior test's response would
        # otherwise leak into this one.
        cache.clear()
        self.author = User.objects.create_user(
            username='api_test_author',
            first_name='API Test',
            last_name='Author',
            email='private-integration-author@example.test',
        )
        self.element = IntegrationElement.objects.create(
            code='compute_roadmap',
            label='ACCESS Allocated Production Compute - Integration Roadmap',
        )
        self.published = IntegrationNews.objects.create(
            title='Published item',
            content='Published content',
            news_type='software_release',
            integration_news_id=900,
            effective_date='2024-01-15',
            author=self.author,
            status='published',
            is_active=True,
        )
        self.published.affected_elements.set([self.element])
        self.draft = IntegrationNews.objects.create(
            title='Draft item',
            content='Draft content',
            news_type='software_release',
            integration_news_id=901,
            author=self.author,
            status='draft',
            is_active=True,
        )
        self.inactive = IntegrationNews.objects.create(
            title='Inactive item',
            content='Inactive content',
            news_type='software_release',
            integration_news_id=902,
            author=self.author,
            status='published',
            is_active=False,
        )

    def test_only_published_active_items_included(self):
        response = self.client.get('/api/integration_news')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        news_ids = {item['integration_news_id'] for item in data}

        self.assertIn(str(self.published.integration_news_id), news_ids)
        self.assertNotIn(str(self.draft.integration_news_id), news_ids)
        self.assertNotIn(str(self.inactive.integration_news_id), news_ids)

    def test_api_url_name_resolves_to_unversioned_path(self):
        self.assertEqual(
            reverse('integration_news:api_integration_news'),
            '/api/integration_news',
        )

    def test_published_item_field_shape(self):
        response = self.client.get('/api/integration_news')
        data = json.loads(response.content)
        item = next(
            i for i in data if i['integration_news_id'] == str(self.published.integration_news_id)
        )

        self.assertNotEqual(self.published.pk, self.published.integration_news_id)
        self.assertEqual(item['integration_news_id'], '900')
        self.assertEqual(item['subject'], 'Published item')
        self.assertEqual(item['type'], 'Software Release')
        self.assertEqual(item['effective_date'], '2024-01-15')
        self.assertEqual(
            item['affected_integration_element'],
            [{'title': 'ACCESS Allocated Production Compute - Integration Roadmap'}],
        )
        self.assertEqual(
            sorted(item.keys()),
            sorted([
                'subject', 'type', 'content', 'effective_date', 'web_url',
                'integration_news_id', 'distribution_options', 'affected_integration_element',
            ]),
        )

    def test_items_are_ordered_by_stable_integration_news_id_with_nulls_last(self):
        IntegrationNews.objects.create(
            title='Earlier stable identifier',
            content='Earlier identifier content',
            news_type='software_release',
            integration_news_id=100,
            author=self.author,
            status='published',
            is_active=True,
        )
        IntegrationNews.objects.create(
            title='Missing stable identifier',
            content='Missing identifier content',
            news_type='software_release',
            integration_news_id=None,
            author=self.author,
            status='published',
            is_active=True,
        )

        response = self.client.get('/api/integration_news')
        data = json.loads(response.content)

        self.assertEqual(
            [item['integration_news_id'] for item in data], ['100', '900', None]
        )

    def test_anonymous_page_and_api_use_the_same_public_filter(self):
        page_response = self.client.get('/integration-news/')
        api_response = self.client.get('/api/integration_news')

        page_news_ids = {
            str(item.integration_news_id) if item.integration_news_id is not None else None
            for item in page_response.context['integration_news']
        }
        api_news_ids = {
            item['integration_news_id'] for item in json.loads(api_response.content)
        }

        self.assertEqual(page_news_ids, api_news_ids)

    def test_old_versioned_api_url_is_not_exposed(self):
        response = self.client.get('/api/integration_news_v1')

        self.assertEqual(response.status_code, 404)
