from django.db import models


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
        permissions = [
            ('rp_coordinator', 'Can coordinate resource provider activities'),
            ('rp_implementer', 'Can implement resource provider tasks'),
        ]

    def __str__(self):
        return self.group_descriptive_name
