from django.contrib.auth.models import User
from django.test import RequestFactory, SimpleTestCase, TestCase

from . import workflow
from .models import IntegrationNews


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
