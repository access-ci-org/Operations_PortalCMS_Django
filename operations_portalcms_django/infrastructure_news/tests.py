import json

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase

from . import workflow
from .models import SystemStatusNews


class AuthenticatedReviewer:
    is_authenticated = True
    is_active = True
    is_superuser = True

    def has_perm(self, _perm):
        return True

    def has_perms(self, _perms):
        return True


class SystemStatusWorkflowMethodTests(SimpleTestCase):
    def setUp(self):
        self.factory = RequestFactory()

    def test_workflow_state_changes_reject_get_requests(self):
        views = [
            workflow.submit_systemstatus_for_review,
            workflow.approve_systemstatus_news,
            workflow.reject_systemstatus_news,
            workflow.publish_systemstatus_news,
            workflow.unpublish_systemstatus_news,
        ]

        for view in views:
            with self.subTest(view=view.__name__):
                request = self.factory.get('/infrastructure-news/1/state/')
                request.user = AuthenticatedReviewer()

                response = view(request, pk=1)

                self.assertEqual(response.status_code, 405)


class ApiInfrastructureNewsTests(TestCase):
    def setUp(self):
        # @cache_page on the view caches the full response process-wide, independent
        # of each test's transaction rollback, so a prior test's response would
        # otherwise leak into this one.
        cache.clear()
        self.author = User.objects.create_user(username='api_test_author')
        self.published = SystemStatusNews.objects.create(
            subject='Published item',
            content='Published content',
            infrastructure_news_type='outage_partial',
            author=self.author,
            status='published',
            is_active=True,
        )
        self.draft = SystemStatusNews.objects.create(
            subject='Draft item',
            content='Draft content',
            infrastructure_news_type='outage_partial',
            author=self.author,
            status='draft',
            is_active=True,
        )

    def test_only_published_active_items_included(self):
        response = self.client.get('/api/infrastructure_news')
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        outage_ids = {item['outage_id'] for item in data}

        self.assertIn(str(self.published.pk), outage_ids)
        self.assertNotIn(str(self.draft.pk), outage_ids)

    def test_published_item_field_shape(self):
        response = self.client.get('/api/infrastructure_news')
        data = json.loads(response.content)
        item = next(i for i in data if i['outage_id'] == str(self.published.pk))

        self.assertEqual(item['subject'], 'Published item')
        self.assertEqual(item['type'], 'Outage Partial')
        self.assertEqual(
            sorted(item.keys()),
            sorted([
                'subject', 'type', 'content', 'start_timestamp', 'end_timestamp',
                'web_url', 'outage_id', 'distribution_options', 'affected_infrastructure',
            ]),
        )
