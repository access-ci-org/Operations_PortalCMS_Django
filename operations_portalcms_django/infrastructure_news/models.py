from cms.models.pluginmodel import CMSPlugin
from django.contrib.auth.models import User
from django.db import IntegrityError, models, router, transaction
from django.db.models import Max
from djangocms_text_ckeditor.fields import HTMLField
from portal.news_distribution import DISTRIBUTION_OPTION_FIELDS

NEWS_TIME_ZONE = "America/Chicago"

FIRST_AUTO_OUTAGE_ID = 2000
OUTAGE_ID_ALLOCATION_ATTEMPTS = 10


def _next_outage_id(using):
    current_max = SystemStatusNews.objects.using(using).aggregate(max_id=Max("outage_id"))["max_id"]
    return max(FIRST_AUTO_OUTAGE_ID, (current_max or FIRST_AUTO_OUTAGE_ID - 1) + 1)


class SystemStatusNews(models.Model):
    """News items related to system status, infrastructure, maintenance, outages, etc."""

    INFRASTRUCTURE_NEWS_TYPES = [
        ("degraded", "Degraded"),
        ("introduction", "Introduction"),
        ("outage_full", "Outage Full"),
        ("outage_partial", "Outage Partial"),
        ("reconfiguration", "Reconfiguration"),
        ("retirement", "Retirement"),
    ]

    DISTRIBUTION_OPTIONS = tuple((field_name, label) for field_name, label, _ in DISTRIBUTION_OPTION_FIELDS)

    subject = models.CharField(max_length=200, default="Untitled", verbose_name="Subject")
    content = HTMLField(verbose_name="News Content")
    infrastructure_news_type = models.CharField(
        max_length=50,
        choices=INFRASTRUCTURE_NEWS_TYPES,
        default="outage_full",
        verbose_name="Infrastructure News Type",
    )
    affected_infrastructure = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Affected Infrastructure",
        help_text="Resource ID(s) from CIDER (comma-separated if multiple)",
    )
    affected_infrastructure_items = models.ManyToManyField(
        "resources.CiderInfrastructure",
        blank=True,
        related_name="system_status_news_items",
        verbose_name="Affected Infrastructure Items",
    )
    start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Start Date and Time",
        help_text="Enter and display in Central Time (America/Chicago).",
    )
    end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="End Date and Time",
        help_text="Enter and display in Central Time (America/Chicago). May be left blank for permanent configuration changes.",
    )
    schedule_timezone = models.CharField(
        max_length=64,
        default=NEWS_TIME_ZONE,
        editable=False,
        verbose_name="Schedule Time Zone",
        help_text="IANA time zone used to enter and display the start and end dates.",
    )
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    outage_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        unique=True,
        db_index=True,
        verbose_name="Outage ID",
        help_text="Stable external identifier used by API consumers. Carried from Drupal for imported records; auto-assigned for new records.",
    )
    distribution_email_everyone = models.BooleanField(default=False, verbose_name="Email everyone with access")
    distribution_email_subscribers = models.BooleanField(default=False, verbose_name="Email only subscribers")
    distribution_post_to_slack = models.BooleanField(default=False, verbose_name="Post to Slack")
    send_email = models.BooleanField(default=False, verbose_name="Send Email Notification")
    email_list = models.CharField(max_length=500, blank=True, verbose_name="Email Recipients")
    post_to_slack = models.BooleanField(default=False, verbose_name="Post to Slack")
    slack_channel = models.CharField(max_length=100, blank=True, verbose_name="Slack Channel")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name="authored_systemstatus_news")
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
        related_name="reviewed_systemstatus_news",
        help_text="User assigned to review this news",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True, help_text="Comments from reviewer")
    published_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_systemstatus_news",
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-start_datetime"]
        verbose_name = "System and Infrastructure Status News"
        verbose_name_plural = "System and Infrastructure Status News"
        db_table = "portal_systemstatusnews"
        permissions = [
            ("can_publish_systemstatusnews", "Can publish System Status News"),
        ]

    def __str__(self):
        return self.subject

    def save(self, *args, **kwargs):
        """Assign a stable external ID to new records when one was not supplied."""
        if self._state.adding and self.outage_id is None:
            using = kwargs.get("using") or router.db_for_write(type(self), instance=self)
            for _attempt in range(OUTAGE_ID_ALLOCATION_ATTEMPTS):
                candidate = _next_outage_id(using)
                self.outage_id = candidate
                try:
                    with transaction.atomic(using=using):
                        return super().save(*args, **kwargs)
                except IntegrityError:
                    # Another writer may have claimed the same max + 1 value
                    # after our query. Retry only when that candidate now exists;
                    # re-raise unrelated integrity failures unchanged.
                    candidate_is_taken = type(self).objects.using(using).filter(outage_id=candidate).exists()
                    self.outage_id = None
                    if not candidate_is_taken:
                        raise

            raise IntegrityError(
                f"Could not allocate a unique outage_id after {OUTAGE_ID_ALLOCATION_ATTEMPTS} attempts."
            )

        return super().save(*args, **kwargs)

    def get_distribution_options(self):
        return [label for field_name, label in self.DISTRIBUTION_OPTIONS if getattr(self, field_name)]

    def get_affected_infrastructure_values(self):
        related_items = sorted(
            self.affected_infrastructure_items.all(), key=lambda item: item.resource_descriptive_name or ""
        )
        values = [item.info_resourceid for item in related_items]
        known_values = set(values)
        if self.affected_infrastructure:
            for value in self.affected_infrastructure.split(","):
                value = value.strip()
                if value and value not in known_values:
                    values.append(value)
                    known_values.add(value)
        return values

    def get_affected_infrastructure_display(self):
        values = self.get_affected_infrastructure_values()
        return ", ".join(values) if values else "N/A"

    def get_infrastructure_type_display_color(self):
        colors = {
            "degraded": "warning",
            "introduction": "info",
            "outage_full": "danger",
            "outage_partial": "warning",
            "reconfiguration": "info",
            "retirement": "secondary",
        }
        return colors.get(self.infrastructure_news_type, "secondary")


class SystemStatusNewsItemPlugin(CMSPlugin):
    """Model for System Status News items added via CMS"""

    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_date"]
        db_table = "portal_systemstatusnewsitemplugin"

    def __str__(self):
        return self.title
