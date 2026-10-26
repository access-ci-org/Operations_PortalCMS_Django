import json
from datetime import datetime
from datetime import timezone as datetime_timezone

from django.contrib.auth.models import User
from django.core.cache import cache
from django.test import RequestFactory, SimpleTestCase, TestCase
from django.urls import reverse

from resources.models import CiderInfrastructure

from . import workflow
from .forms import SystemStatusNewsForm
from .models import SystemStatusNews
from .services import _format_timestamp


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
            workflow.publish_systemstatus_news,
            workflow.unpublish_systemstatus_news,
        ]

        for view in views:
            with self.subTest(view=view.__name__):
                request = self.factory.get("/infrastructure-news/1/state/")
                request.user = AuthenticatedReviewer()

                response = view(request, pk=1)

                self.assertEqual(response.status_code, 405)


class SystemStatusNewsFormTests(SimpleTestCase):
    def test_affected_infrastructure_is_ordered_and_labeled_by_description(self):
        form = SystemStatusNewsForm()
        field = form.fields["affected_infrastructure_items"]
        infrastructure = CiderInfrastructure(
            cider_resource_id=1,
            cider_type="resource",
            info_resourceid="allocations.access-ci.org",
            info_siteid="access",
            resource_descriptive_name="ACCESS Allocations Portal",
        )

        self.assertEqual(field.queryset.query.order_by, ("resource_descriptive_name",))
        self.assertEqual(
            field.label_from_instance(infrastructure),
            "ACCESS Allocations Portal - allocations.access-ci.org",
        )

    def test_distribution_options_use_requested_labels(self):
        form = SystemStatusNewsForm()

        self.assertEqual(form.fields["email_notification"].label, "Email everyone with access")
        self.assertEqual(form.fields["subscriber_notification"].label, "Email only subscribers")
        self.assertEqual(form.fields["slack_notification"].label, "Post to Slack")


class SystemStatusNewsDistributionPersistenceTests(TestCase):
    def setUp(self):
        self.author = User.objects.create_user(username="distribution_author")

    def _form_data(self, **overrides):
        data = {
            "subject": "Distribution test",
            "content": "Saved distribution content",
            "infrastructure_news_type": "degraded",
            "start_datetime": "2026-10-26T09:00",
            "email_notification": "on",
            "subscriber_notification": "on",
            "slack_notification": "on",
            "is_active": "on",
        }
        data.update(overrides)
        return data

    def test_create_and_edit_preserve_independent_distribution_options(self):
        form = SystemStatusNewsForm(data=self._form_data())
        self.assertTrue(form.is_valid(), form.errors)
        news = form.save(commit=False)
        news.author = self.author
        news.save()
        form.save_related_fields(news)

        news.refresh_from_db()
        self.assertTrue(news.distribution_email_everyone)
        self.assertTrue(news.distribution_email_subscribers)
        self.assertTrue(news.distribution_post_to_slack)

        edit_form = SystemStatusNewsForm(instance=news)
        self.assertTrue(edit_form.fields["email_notification"].initial)
        self.assertTrue(edit_form.fields["subscriber_notification"].initial)
        self.assertTrue(edit_form.fields["slack_notification"].initial)

        update = SystemStatusNewsForm(
            data=self._form_data(email_notification="", slack_notification=""),
            instance=news,
        )
        self.assertTrue(update.is_valid(), update.errors)
        news = update.save()
        update.save_related_fields(news)
        news.refresh_from_db()

        self.assertFalse(news.distribution_email_everyone)
        self.assertTrue(news.distribution_email_subscribers)
        self.assertFalse(news.distribution_post_to_slack)


class ApiTimestampFormattingTests(SimpleTestCase):
    def test_formats_winter_timestamp_in_central_standard_time(self):
        value = datetime(2024, 1, 15, 12, 0, tzinfo=datetime_timezone.utc)

        self.assertEqual(_format_timestamp(value), "2024-01-15T06:00:00-0600")

    def test_formats_summer_timestamp_in_central_daylight_time(self):
        value = datetime(2024, 7, 15, 12, 0, tzinfo=datetime_timezone.utc)

        self.assertEqual(_format_timestamp(value), "2024-07-15T07:00:00-0500")

    def test_formats_naive_timestamp_as_utc(self):
        value = datetime(2024, 7, 15, 12, 0)

        self.assertEqual(_format_timestamp(value), "2024-07-15T07:00:00-0500")

    def test_formats_missing_timestamp_as_empty_string(self):
        self.assertEqual(_format_timestamp(None), "")


class InfrastructureNewsUrlTests(SimpleTestCase):
    def test_page_url_name_resolves_to_infrastructure_news_view_path(self):
        self.assertEqual(
            reverse("infrastructure_news:system_status_news"),
            "/infrastructure_news_view",
        )

    def test_add_url_name_resolves_to_infrastructure_news_path(self):
        self.assertEqual(
            reverse("infrastructure_news:add_system_status_news"),
            "/infrastructure_news/add/",
        )

    def test_update_url_name_resolves_to_infrastructure_news_path(self):
        self.assertEqual(
            reverse("infrastructure_news:update_system_status_news", args=[286]),
            "/infrastructure_news/update/286/",
        )


class ApiInfrastructureNewsTests(TestCase):
    def setUp(self):
        # @cache_page on the view caches the full response process-wide, independent
        # of each test's transaction rollback, so a prior test's response would
        # otherwise leak into this one.
        cache.clear()
        self.author = User.objects.create_user(
            username="api_test_author",
            first_name="API Test",
            last_name="Author",
            email="private-infrastructure-author@example.test",
        )
        self.published = SystemStatusNews.objects.create(
            subject="Published item",
            content="Published content",
            infrastructure_news_type="outage_partial",
            outage_id=900,
            start_datetime=datetime(2024, 1, 15, 12, 0, tzinfo=datetime_timezone.utc),
            end_datetime=datetime(2024, 7, 15, 12, 0, tzinfo=datetime_timezone.utc),
            author=self.author,
            status="published",
            is_active=True,
            distribution_email_everyone=True,
            distribution_email_subscribers=True,
            distribution_post_to_slack=True,
        )
        self.draft = SystemStatusNews.objects.create(
            subject="Draft item",
            content="Draft content",
            infrastructure_news_type="outage_partial",
            outage_id=901,
            author=self.author,
            status="draft",
            is_active=True,
        )
        self.inactive = SystemStatusNews.objects.create(
            subject="Inactive item",
            content="Inactive content",
            infrastructure_news_type="outage_partial",
            outage_id=902,
            author=self.author,
            status="published",
            is_active=False,
        )

    def test_only_published_active_items_included(self):
        response = self.client.get("/api/infrastructure_news_v1")
        self.assertEqual(response.status_code, 200)

        data = json.loads(response.content)
        outage_ids = {item["outage_id"] for item in data}

        self.assertIn(str(self.published.outage_id), outage_ids)
        self.assertNotIn(str(self.draft.outage_id), outage_ids)
        self.assertNotIn(str(self.inactive.outage_id), outage_ids)

    def test_api_url_name_resolves_to_versioned_path(self):
        self.assertEqual(
            reverse("infrastructure_news:api_infrastructure_news"),
            "/api/infrastructure_news_v1",
        )

    def test_published_item_field_shape(self):
        response = self.client.get("/api/infrastructure_news_v1")
        data = json.loads(response.content)
        item = next(i for i in data if i["outage_id"] == str(self.published.outage_id))

        self.assertNotEqual(self.published.pk, self.published.outage_id)
        self.assertEqual(item["outage_id"], "900")
        self.assertEqual(item["subject"], "Published item")
        self.assertEqual(item["type"], "Outage Partial")
        self.assertEqual(item["start_timestamp"], "2024-01-15T06:00:00-0600")
        self.assertEqual(item["end_timestamp"], "2024-07-15T07:00:00-0500")
        self.assertEqual(
            item["distribution_options"],
            "Email everyone with access, Email only subscribers, Post to Slack",
        )
        self.assertEqual(
            sorted(item.keys()),
            sorted(
                [
                    "subject",
                    "type",
                    "content",
                    "start_timestamp",
                    "end_timestamp",
                    "web_url",
                    "outage_id",
                    "distribution_options",
                    "affected_infrastructure",
                ]
            ),
        )

    def test_distribution_options_match_legacy_two_value_format(self):
        self.published.distribution_email_everyone = False
        self.published.save(update_fields=["distribution_email_everyone"])

        response = self.client.get("/api/infrastructure_news_v1")
        data = json.loads(response.content)
        item = next(i for i in data if i["outage_id"] == str(self.published.outage_id))

        self.assertEqual(item["distribution_options"], "Email only subscribers, Post to Slack")

    def test_items_are_ordered_by_stable_outage_id_with_nulls_last(self):
        SystemStatusNews.objects.create(
            subject="Earlier stable identifier",
            content="Earlier identifier content",
            infrastructure_news_type="degraded",
            outage_id=100,
            author=self.author,
            status="published",
            is_active=True,
        )
        SystemStatusNews.objects.create(
            subject="Missing stable identifier",
            content="Missing identifier content",
            infrastructure_news_type="degraded",
            outage_id=None,
            author=self.author,
            status="published",
            is_active=True,
        )

        response = self.client.get("/api/infrastructure_news_v1")
        data = json.loads(response.content)

        self.assertEqual([item["outage_id"] for item in data], ["100", "900", None])
        missing_timestamp_item = next(item for item in data if item["outage_id"] is None)
        self.assertEqual(missing_timestamp_item["start_timestamp"], "")
        self.assertEqual(missing_timestamp_item["end_timestamp"], "")

    def test_anonymous_page_and_api_use_the_same_public_filter(self):
        page_response = self.client.get("/infrastructure_news_view")
        api_response = self.client.get("/api/infrastructure_news_v1")

        page_outage_ids = {
            str(item.outage_id) if item.outage_id is not None else None
            for item in page_response.context["system_status_news"]
        }
        api_outage_ids = {item["outage_id"] for item in json.loads(api_response.content)}

        self.assertEqual(page_outage_ids, api_outage_ids)

    def test_unversioned_api_url_is_not_exposed(self):
        response = self.client.get("/api/infrastructure_news")

        self.assertEqual(response.status_code, 404)

    def test_anonymous_page_shows_published_author_name_without_email(self):
        response = self.client.get("/infrastructure_news_view")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Author: API Test Author")
        self.assertNotContains(response, self.author.email)
