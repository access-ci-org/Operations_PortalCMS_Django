from django.db import models


class CiderInfrastructure(models.Model):
    """Local projection of CIDER infrastructure resources (compute, storage, cloud, etc.).

    IMPORTANT: This model is a non-authoritative read-only cache.
    Operations_Warehouse_Django/cider is the authoritative source. Data here is
    populated exclusively by the sync_cider_from_api management command, which
    pulls from the Warehouse-hosted Operations API. Do not edit rows via the admin
    or application code — use the sync command instead.

    These rows exist to support:
    - infrastructure_news many-to-many relationships and selectors
    - historical news record display
    - Resource Provider permission setup (via CiderGroups)

    Public resource listings and detail pages must use the Warehouse API directly,
    not these local rows.
    """
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
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text='False when the resource is no longer present in the Warehouse API. '
                  'Inactive rows are retained so historical news relationships remain readable.',
    )

    class Meta:
        db_table = 'cider_infrastructure'
        verbose_name = 'CIDER Infrastructure'
        verbose_name_plural = 'CIDER Infrastructure'
        ordering = ['resource_descriptive_name']

    def __str__(self):
        return f"{self.info_resourceid} - {self.resource_descriptive_name}"


class CiderOrganizations(models.Model):
    """Local projection of CIDER organizations (sites, institutions).

    Non-authoritative cache — see CiderInfrastructure docstring for details.
    Populated exclusively by sync_cider_from_api.
    """
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
    """Local projection of CIDER feature categories (capabilities, specifications).

    Non-authoritative cache — see CiderInfrastructure docstring for details.
    Populated exclusively by sync_cider_from_api.
    """
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
    """Local projection of CIDER Resource Provider groups.

    Non-authoritative cache — see CiderInfrastructure docstring for details.
    Populated exclusively by sync_cider_from_api. Used locally to drive
    Django permission and auth group setup via setup_rp_permissions.
    """
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
