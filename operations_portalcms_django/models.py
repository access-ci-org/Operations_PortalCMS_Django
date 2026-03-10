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


# ==================== CIDER Models ====================
# Models synced from CIDER API for infrastructure, resources, and groups

class CiderInfrastructure(models.Model):
    """Infrastructure resources from CIDER - compute, storage, cloud, etc."""
    cider_resource_id = models.IntegerField(primary_key=True)
    cider_type = models.CharField(max_length=16)
    info_resourceid = models.CharField(db_index=True, max_length=40)
    info_siteid = models.CharField(db_index=True, max_length=40)
    resource_descriptive_name = models.CharField(max_length=120)
    resource_description = models.CharField(max_length=4000, null=True, blank=True)
    resource_status = models.JSONField(null=True, blank=True)
    current_statuses = models.CharField(max_length=64, blank=True)
    latest_status = models.CharField(max_length=32, null=True, blank=True)
    latest_status_begin = models.DateField(null=True, blank=True)
    latest_status_end = models.DateField(null=True, blank=True)
    parent_resource = models.IntegerField(db_index=True, null=True, blank=True)
    recommended_use = models.CharField(max_length=4000, null=True, blank=True)
    access_description = models.CharField(max_length=4000, null=True, blank=True)
    project_affiliation = models.CharField(max_length=64, null=True, blank=True)
    provider_level = models.CharField(max_length=16, null=True, blank=True)
    protected_attributes = models.JSONField(null=True, blank=True)
    other_attributes = models.JSONField(null=True, blank=True)
    updated_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'cider_infrastructure'
        verbose_name = 'CIDER Infrastructure'
        verbose_name_plural = 'CIDER Infrastructure'
        ordering = ['resource_descriptive_name']
    
    def __str__(self):
        return f"{self.info_resourceid} - {self.resource_descriptive_name}"


class CiderOrganizations(models.Model):
    """Organizations (sites, institutions) from CIDER"""
    organization_id = models.IntegerField(primary_key=True)
    organization_name = models.CharField(max_length=120)
    organization_abbrev = models.CharField(max_length=20, blank=True)
    organization_url = models.CharField(max_length=320, null=True, blank=True)
    other_attributes = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'cider_organizations'
        verbose_name = 'CIDER Organization'
        verbose_name_plural = 'CIDER Organizations'
        ordering = ['organization_name']
    
    def __str__(self):
        return self.organization_name


class CiderFeatures(models.Model):
    """Feature categories (capabilities, specifications) from CIDER"""
    feature_category_id = models.IntegerField(primary_key=True)
    feature_category_name = models.CharField(max_length=120)
    feature_category_description = models.CharField(max_length=4000, null=True, blank=True)
    feature_category_types = models.JSONField(null=True, blank=True)
    features = models.JSONField(null=True, blank=True)
    other_attributes = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'cider_features'
        verbose_name = 'CIDER Feature Category'
        verbose_name_plural = 'CIDER Feature Categories'
        ordering = ['feature_category_name']
    
    def __str__(self):
        return self.feature_category_name


class CiderGroups(models.Model):
    """Resource Provider groups from CIDER - used for permissions"""
    group_id = models.IntegerField(primary_key=True)
    info_groupid = models.CharField(db_index=True, max_length=40, unique=True)
    group_descriptive_name = models.CharField(max_length=120)
    group_description = models.CharField(max_length=4000, null=True, blank=True)
    group_logo_url = models.CharField(max_length=320, null=True, blank=True)
    group_types = models.JSONField(null=True, blank=True)
    info_resourceids = models.JSONField(null=True, blank=True)
    other_attributes = models.JSONField(null=True, blank=True)
    
    class Meta:
        db_table = 'cider_groups'
        verbose_name = 'CIDER Group'
        verbose_name_plural = 'CIDER Groups'
        ordering = ['group_descriptive_name']
        # Custom permissions for RP roles
        permissions = [
            ('rp_coordinator', 'Can coordinate resource provider activities'),
            ('rp_implementer', 'Can implement resource provider tasks'),
        ]
    
    def __str__(self):
        return f"{self.info_groupid} - {self.group_descriptive_name}"
