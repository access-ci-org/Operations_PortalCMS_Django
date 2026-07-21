from types import SimpleNamespace
from unittest import mock

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.test import TestCase
from django.urls import reverse

from djangocms_versioning.constants import DRAFT, PUBLISHED


class SubmitPageDraftForReviewTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.owner = User.objects.create_user(
            username="owner", password="password", is_staff=True
        )
        self.other_staff = User.objects.create_user(
            username="other", password="password", is_staff=True
        )
        self.non_staff = User.objects.create_user(
            username="nonstaff", password="password", is_staff=False
        )
        self.url = reverse("portal:submit_page_draft_for_review", args=[123])

    def _version(self, *, state=DRAFT, locked_by_id=None):
        return SimpleNamespace(
            pk=123,
            state=state,
            locked_by_id=locked_by_id,
            content=object(),
        )

    def _post_with_version(self, user, version):
        self.client.force_login(user)
        with mock.patch("portal.views.get_object_or_404", return_value=version), mock.patch(
            "portal.views.version_list_url", return_value="/versions/"
        ), mock.patch("portal.views.remove_version_lock") as remove_lock:
            response = self.client.post(self.url)
        return response, remove_lock

    def test_get_is_not_allowed_for_staff(self):
        self.client.force_login(self.owner)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 405)

    def test_non_staff_is_redirected_to_admin_login(self):
        self.client.force_login(self.non_staff)

        response = self.client.post(self.url)

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("admin:login"), response.url)

    def test_owner_can_submit_own_draft_without_global_unlock_permission(self):
        version = self._version(locked_by_id=self.owner.pk)

        response, remove_lock = self._post_with_version(self.owner, version)

        self.assertRedirects(
            response,
            "/versions/",
            fetch_redirect_response=False,
        )
        remove_lock.assert_called_once_with(version)
        self.assertEqual(version.state, DRAFT)
        self.assertFalse(
            self.owner.has_perm("djangocms_versioning.delete_versionlock")
        )

    def test_user_cannot_submit_another_users_locked_draft(self):
        version = self._version(locked_by_id=self.owner.pk)

        response, remove_lock = self._post_with_version(self.other_staff, version)

        self.assertEqual(response.status_code, 403)
        remove_lock.assert_not_called()

    def test_unlock_permission_allows_reviewer_to_release_foreign_lock(self):
        unlock_permission = Permission.objects.get(
            content_type__app_label="djangocms_versioning",
            content_type__model="version",
            codename="delete_versionlock",
        )
        self.other_staff.user_permissions.add(unlock_permission)
        version = self._version(locked_by_id=self.owner.pk)

        response, remove_lock = self._post_with_version(self.other_staff, version)

        self.assertEqual(response.status_code, 302)
        remove_lock.assert_called_once_with(version)

    def test_non_draft_is_not_submitted(self):
        version = self._version(state=PUBLISHED, locked_by_id=self.owner.pk)

        response, remove_lock = self._post_with_version(self.owner, version)

        self.assertEqual(response.status_code, 302)
        remove_lock.assert_not_called()
