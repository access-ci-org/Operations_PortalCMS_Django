from django.test import RequestFactory, SimpleTestCase

from . import workflow


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
