from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
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
    
    # Basic fields
    subject = models.CharField(max_length=200, default='Untitled', verbose_name="Subject")
    content = models.TextField(verbose_name="News Content")
    
    # Infrastructure-specific fields
    infrastructure_news_type = models.CharField(
        max_length=50,
        choices=INFRASTRUCTURE_NEWS_TYPES,
        default='outage_full',
        verbose_name="Infrastructure News Type"
    )
    affected_infrastructure = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Affected Infrastructure",
        help_text="Resource ID(s) from CIDER (comma-separated if multiple)"
    )
    
    # Date/Time fields
    start_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Start Date and Time",
        help_text="When the infrastructure outage or reconfiguration starts (in your local timezone)"
    )
    end_datetime = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="End Date and Time",
        help_text="When this outage or configuration change ends. May be left blank for permanent configuration changes."
    )
    
    # Legacy date fields for compatibility (can be removed after migration)
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    
    # Distribution options
    send_email = models.BooleanField(default=False, verbose_name="Send Email Notification")
    email_list = models.CharField(
        max_length=500,
        blank=True,
        verbose_name="Email Recipients",
        help_text="Comma-separated email addresses"
    )
    post_to_slack = models.BooleanField(default=False, verbose_name="Post to Slack")
    slack_channel = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Slack Channel",
        help_text="e.g., #operations-alerts"
    )
    
    # Meta fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-start_datetime']
        verbose_name = 'System and Infrastructure Status News'
        verbose_name_plural = 'System and Infrastructure Status News'
        db_table = 'operations_portalcms_django_systemstatusnews'
    
    def __str__(self):
        return self.subject
    
    def get_infrastructure_type_display_color(self):
        """Return a color class based on the infrastructure news type"""
        colors = {
            'degraded': 'warning',
            'introduction': 'info',
            'outage_full': 'danger',
            'outage_partial': 'warning',
            'reconfiguration': 'info',
            'retirement': 'secondary',
        }
        return colors.get(self.infrastructure_news_type, 'secondary')


class IntegrationNews(models.Model):
    """News items related to integrations, resource connections, new services, etc."""
    title = models.CharField(max_length=200)
    content = models.TextField()
    news_type = models.CharField(max_length=50, blank=True)
    affected_element = models.CharField(max_length=100, blank=True)
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Integration News'
        verbose_name_plural = 'Integration News'
        db_table = 'operations_portalcms_django_integrationnews'
    
    def __str__(self):
        return self.title


# CMS Plugin Models for News Feed

class SystemStatusNewsItemPlugin(CMSPlugin):
    """Model for System Status News items added via CMS"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-published_date']  # Newest first
    
    def __str__(self):
        return self.title


class IntegrationNewsItemPlugin(CMSPlugin):
    """Model for Integration News items added via CMS"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-published_date']  # Newest first
    
    def __str__(self):
        return self.title
