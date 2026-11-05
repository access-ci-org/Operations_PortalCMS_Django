from cms.models.pluginmodel import CMSPlugin
from django.contrib.auth.models import User
from django.db import IntegrityError, models, router, transaction
from django.db.models import Max
from djangocms_text_ckeditor.fields import HTMLField
from portal.news_distribution import DISTRIBUTION_OPTION_FIELDS

FIRST_AUTO_INTEGRATION_NEWS_ID = 2000
INTEGRATION_NEWS_ID_ALLOCATION_ATTEMPTS = 10


def _next_integration_news_id(using):
    current_max = IntegrationNews.objects.using(using).aggregate(max_id=Max("integration_news_id"))["max_id"]
    return max(FIRST_AUTO_INTEGRATION_NEWS_ID, (current_max or FIRST_AUTO_INTEGRATION_NEWS_ID - 1) + 1)


class IntegrationElement(models.Model):
    """Normalized integration element choices for multi-select news relationships."""

    code = models.CharField(max_length=100, primary_key=True)
    label = models.CharField(max_length=200)

    class Meta:
        db_table = "portal_integrationelement"
        verbose_name = "Integration Element"
        verbose_name_plural = "Integration Elements"
        ordering = ["label"]

    def __str__(self):
        return self.label


class IntegrationNews(models.Model):
    """News items related to integrations, resource connections, new services, etc."""

    INTEGRATION_NEWS_TYPES = [
        ("software_release", "Software Release"),
        ("new_roadmap", "New Integration Roadmap"),
        ("changed_roadmap", "Changed Integration Roadmap"),
        ("new_roadmap_task", "New Integration Roadmap Task"),
        ("changed_roadmap_task", "Changed Integration Roadmap Task"),
    ]

    AFFECTED_ELEMENTS = [
        ("cloud_roadmap", "ACCESS Allocated Production Cloud - Integration Roadmap"),
        ("compute_roadmap", "ACCESS Allocated Production Compute - Integration Roadmap"),
        ("storage_roadmap", "ACCESS Allocated Production Storage - Integration Roadmap"),
        ("science_gateway_roadmap", "ACCESS Integrated Science Gateway - Integration Roadmap"),
        ("nagios", "ACCESS Monitoring Service - Nagios"),
        ("online_service_roadmap", "ACCESS Production Online Service - Integration Roadmap"),
        ("aws_registry", "ACCESS Public AWS Container Registry"),
        ("cider", "CiDeR - CyberInfrastructure Description Repository"),
        ("ipf", "Information Publishing Framework (IPF) tool for publishing compute resource information"),
        ("accessusage", "accessusage - command line allocation usage lookup"),
        ("access_oauth_mapfile", "access-oauth-mapfile - ACCESS OAuth identity to local account mapping"),
        ("access_operations_portal", "ACCESS Operations Portal"),
    ]

    DISTRIBUTION_OPTIONS = tuple((field_name, label) for field_name, label, _ in DISTRIBUTION_OPTION_FIELDS)

    title = models.CharField(max_length=200)
    content = HTMLField()
    news_type = models.CharField(max_length=50, blank=True)
    affected_element = models.CharField(max_length=100, blank=True)
    affected_elements = models.ManyToManyField(
        IntegrationElement,
        blank=True,
        related_name="integration_news_items",
        verbose_name="Affected Elements",
    )
    integration_news_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="Integration News ID",
        help_text="Stable external identifier used by API consumers. Carried from Drupal for imported records; auto-assigned for new records.",
    )
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    distribution_email_everyone = models.BooleanField(default=False, verbose_name="Email everyone with access")
    distribution_email_subscribers = models.BooleanField(default=False, verbose_name="Email only subscribers")
    distribution_post_to_slack = models.BooleanField(default=False, verbose_name="Post to Slack")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="authored_integration_news")
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ("draft", "Draft"),
            ("published", "Published"),
        ],
        default="published",
        help_text="Current workflow status",
    )
    reviewer = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_integration_news",
        help_text="User assigned to review this news",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True, help_text="Comments from reviewer")
    published_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_integration_news",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Integration News"
        verbose_name_plural = "Integration News"
        db_table = "portal_integrationnews"
        permissions = [
            ("can_publish_integrationnews", "Can publish Integration News"),
        ]

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        """Assign a stable external ID to new records when one was not supplied."""
        if self._state.adding and self.integration_news_id is None:
            using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
            for _attempt in range(INTEGRATION_NEWS_ID_ALLOCATION_ATTEMPTS):
                candidate = _next_integration_news_id(using)
                self.integration_news_id = candidate
                try:
                    with transaction.atomic(using=using):
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    # Another writer may have claimed the same max + 1 value
                    # after our query. Retry only when that candidate now exists;
                    # re-raise unrelated integrity failures unchanged.
                    candidate_is_taken = (
                        type(self).objects.using(using).filter(integration_news_id=candidate).exists()
                    )
                    self.integration_news_id = None
                    if not candidate_is_taken:
                        raise

            raise IntegrityError(
                "Could not allocate a unique integration_news_id after "
                f"{INTEGRATION_NEWS_ID_ALLOCATION_ATTEMPTS} attempts."
            )

        return super().save(*args, **kwargs)

    def get_distribution_options(self):
        return [label for field_name, label in self.DISTRIBUTION_OPTIONS if getattr(self, field_name)]

    def get_news_type_label(self):
        return dict(self.INTEGRATION_NEWS_TYPES).get(self.news_type, self.news_type or "N/A")

    def get_affected_element_label(self):
        return dict(self.AFFECTED_ELEMENTS).get(self.affected_element, self.affected_element or "N/A")

    def get_affected_element_labels(self):
        related_items = sorted(self.affected_elements.all(), key=lambda item: item.label or "")
        if related_items:
            return [item.label for item in related_items]
        if not self.affected_element:
            return []
        return [self.get_affected_element_label()]

    def get_affected_elements_display(self):
        labels = self.get_affected_element_labels()
        return ", ".join(labels) if labels else "N/A"


class IntegrationNewsItemPlugin(CMSPlugin):
    """Model for Integration News items added via CMS"""

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_date"]
        db_table = "portal_integrationnewsitemplugin"

    def __str__(self):
        return self.title
