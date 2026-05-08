from django.contrib.auth.models import User
from django.db import models
from cms.models.pluginmodel import CMSPlugin


class SystemStatusNews(models.Model):
    """News items related to system status, infrastructure, maintenance, outages, etc."""

    INFRASTRUCTURE_NEWS_TYPES = [
        ('degraded', 'Degraded'),
        ('introduction', 'Introduction'),
        ('outage_full', 'Outage Full'),
        ('outage_partial', 'Outage Partial'),
        ('reconfiguration', 'Reconfiguration'),
        ('retirement', 'Retirement'),
    ]

    subject = models.CharField(max_length=200, default='Untitled', verbose_name='Subject')
    content = models.TextField(verbose_name='News Content')
    infrastructure_news_type = models.CharField(
        max_length=50,
        choices=INFRASTRUCTURE_NEWS_TYPES,
        default='outage_full',
        verbose_name='Infrastructure News Type',
    )
    affected_infrastructure = models.CharField(
        max_length=255,
        blank=True,
        verbose_name='Affected Infrastructure',
        help_text='Resource ID(s) from CIDER (comma-separated if multiple)',
    )
    affected_infrastructure_items = models.ManyToManyField(
        'resources.CiderInfrastructure',
        blank=True,
        related_name='system_status_news_items',
        verbose_name='Affected Infrastructure Items',
    )
    start_datetime = models.DateTimeField(
        null=True, blank=True,
        verbose_name='Start Date and Time',
        help_text='When the infrastructure outage or reconfiguration starts (in your local timezone)',
    )
    end_datetime = models.DateTimeField(
        null=True, blank=True,
        verbose_name='End Date and Time',
        help_text='When this outage or configuration change ends. May be left blank for permanent configuration changes.',
    )
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    send_email = models.BooleanField(default=False, verbose_name='Send Email Notification')
    email_list = models.CharField(max_length=500, blank=True, verbose_name='Email Recipients')
    post_to_slack = models.BooleanField(default=False, verbose_name='Post to Slack')
    slack_channel = models.CharField(max_length=100, blank=True, verbose_name='Slack Channel')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_systemstatus_news')
    is_active = models.BooleanField(default=True)
    status = models.CharField(
        max_length=20,
        choices=[
            ('draft', 'Draft'),
            ('pending_review', 'Pending Review'),
            ('approved', 'Approved'),
            ('published', 'Published'),
            ('rejected', 'Rejected'),
        ],
        default='published',
        help_text='Current workflow status',
    )
    reviewer = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='reviewed_systemstatus_news',
        help_text='User assigned to review this news',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True, help_text='Comments from reviewer')
    published_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='published_systemstatus_news',
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-start_datetime']
        verbose_name = 'System and Infrastructure Status News'
        verbose_name_plural = 'System and Infrastructure Status News'
        db_table = 'operations_portalcms_django_systemstatusnews'
        permissions = [
            ('can_review_systemstatusnews', 'Can review System Status News'),
            ('can_publish_systemstatusnews', 'Can publish System Status News'),
        ]

    def __str__(self):
        return self.subject

    def get_affected_infrastructure_values(self):
        related_items = sorted(
            self.affected_infrastructure_items.all(),
            key=lambda item: item.resource_descriptive_name or ''
        )
        if related_items:
            return [item.info_resourceid for item in related_items]
        if not self.affected_infrastructure:
            return []
        return [v.strip() for v in self.affected_infrastructure.split(',') if v.strip()]

    def get_affected_infrastructure_display(self):
        values = self.get_affected_infrastructure_values()
        return ', '.join(values) if values else 'N/A'

    def get_infrastructure_type_display_color(self):
        colors = {
            'degraded': 'warning',
            'introduction': 'info',
            'outage_full': 'danger',
            'outage_partial': 'warning',
            'reconfiguration': 'info',
            'retirement': 'secondary',
        }
        return colors.get(self.infrastructure_news_type, 'secondary')


class SystemStatusNewsItemPlugin(CMSPlugin):
    """Model for System Status News items added via CMS"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_date']

    def __str__(self):
        return self.title
