from types import SimpleNamespace
from unittest.mock import patch

from allauth.account.adapter import get_adapter as get_account_adapter
from allauth.account.views import SignupView, signup
from allauth.socialaccount.adapter import get_adapter as get_socialaccount_adapter
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory, SimpleTestCase
from django.urls import resolve, reverse


class SignupPolicyTests(SimpleTestCase):
    def setUp(self):
        self.request = RequestFactory().get("/")
        self.request.user = AnonymousUser()
        self.request.session = {}

    def test_local_signup_get_shows_closed_page_without_form(self):
        response = signup(self.request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, "account/signup_closed.html")
        self.assertIsNone(response.context_data)

    def test_local_signup_post_does_not_create_user(self):
        request = RequestFactory().post(
            "/accounts/signup/",
            {
                "username": "new-local-user",
                "email": "new-local-user@example.org",
                "password1": "not-a-real-password-123",
                "password2": "not-a-real-password-123",
            },
        )
        request.user = AnonymousUser()
        request.session = {}

        with patch.object(SignupView, "get_form") as get_form:
            response = signup(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.template_name, "account/signup_closed.html")
        get_form.assert_not_called()

    def test_existing_local_account_login_route_remains_available(self):
        match = resolve(reverse("account_login"))

        self.assertEqual(match.url_name, "account_login")

    def test_local_signup_policy_is_closed(self):
        self.assertFalse(
            get_account_adapter(self.request).is_open_for_signup(self.request)
        )

    def test_cilogon_social_signup_policy_remains_open(self):
        sociallogin = SimpleNamespace(
            account=SimpleNamespace(provider="cilogon"),
        )

        self.assertTrue(
            get_socialaccount_adapter(self.request).is_open_for_signup(
                self.request,
                sociallogin,
            )
        )

    def test_other_social_signup_policies_are_closed(self):
        sociallogin = SimpleNamespace(
            account=SimpleNamespace(provider="other-provider"),
        )

        self.assertFalse(
            get_socialaccount_adapter(self.request).is_open_for_signup(
                self.request,
                sociallogin,
            )
        )

    def test_cilogon_login_route_remains_available(self):
        match = resolve(reverse("cilogon_login"))

        self.assertEqual(match.url_name, "cilogon_login")
