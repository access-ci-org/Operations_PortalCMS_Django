from django.contrib.auth.models import User
from django.db import models
from cms.models.pluginmodel import CMSPlugin


class IntegrationElement(models.Model):
    """Normalized integration element choices for multi-select news relationships."""
    code = models.CharField(max_length=100, primary_key=True)
    label = models.CharField(max_length=200)

    class Meta:
        db_table = 'portal_integrationelement'
        verbose_name = 'Integration Element'
        verbose_name_plural = 'Integration Elements'
        ordering = ['label']

    def __str__(self):
        return self.label


class IntegrationNews(models.Model):
    """News items related to integrations, resource connections, new services, etc."""
    INTEGRATION_NEWS_TYPES = [
        ('software_release', 'Software Release'),
        ('new_roadmap', 'New Integration Roadmap'),
        ('changed_roadmap', 'Changed Integration Roadmap'),
        ('new_roadmap_task', 'New Integration Roadmap Task'),
        ('changed_roadmap_task', 'Changed Integration Roadmap Task'),
    ]

    AFFECTED_ELEMENTS = [
        ('cloud_roadmap', 'ACCESS Allocated Production Cloud - Integration Roadmap'),
        ('compute_roadmap', 'ACCESS Allocated Production Compute - Integration Roadmap'),
        ('storage_roadmap', 'ACCESS Allocated Production Storage - Integration Roadmap'),
        ('science_gateway_roadmap', 'ACCESS Integrated Science Gateway - Integration Roadmap'),
        ('nagios', 'ACCESS Monitoring Service - Nagios'),
        ('online_service_roadmap', 'ACCESS Production Online Service - Integration Roadmap'),
        ('aws_registry', 'ACCESS Public AWS Container Registry'),
        ('cider', 'CiDeR - CyberInfrastructure Description Repository'),
        ('ipf', 'Information Publishing Framework (IPF) tool for publishing compute resource information'),
    ]

    title = models.CharField(max_length=200)
    content = models.TextField()
    news_type = models.CharField(max_length=50, blank=True)
    affected_element = models.CharField(max_length=100, blank=True)
    affected_elements = models.ManyToManyField(
        IntegrationElement,
        blank=True,
        related_name='integration_news_items',
        verbose_name='Affected Elements',
    )
    effective_date = models.DateField(null=True, blank=True)
    expiration_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    author = models.ForeignKey(User, on_delete=models.CASCADE, related_name='authored_integration_news')
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
        related_name='reviewed_integration_news',
        help_text='User assigned to review this news',
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_comments = models.TextField(blank=True, help_text='Comments from reviewer')
    published_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        related_name='published_integration_news',
    )
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Integration News'
        verbose_name_plural = 'Integration News'
        db_table = 'portal_integrationnews'
        permissions = [
            ('can_review_integrationnews', 'Can review Integration News'),
            ('can_publish_integrationnews', 'Can publish Integration News'),
        ]

    def __str__(self):
        return self.title

    def get_news_type_label(self):
        return dict(self.INTEGRATION_NEWS_TYPES).get(self.news_type, self.news_type or 'N/A')

    def get_affected_element_label(self):
        return dict(self.AFFECTED_ELEMENTS).get(self.affected_element, self.affected_element or 'N/A')

    def get_affected_element_labels(self):
        related_items = sorted(self.affected_elements.all(), key=lambda item: item.label or '')
        if related_items:
            return [item.label for item in related_items]
        if not self.affected_element:
            return []
        return [self.get_affected_element_label()]

    def get_affected_elements_display(self):
        labels = self.get_affected_element_labels()
        return ', '.join(labels) if labels else 'N/A'


class IntegrationNewsItemPlugin(CMSPlugin):
    """Model for Integration News items added via CMS"""
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    published_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-published_date']
        db_table = 'portal_integrationnewsitemplugin'

    def __str__(self):
        return self.title
