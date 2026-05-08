"""
Initial migration for the `resources` app.

Uses SeparateDatabaseAndState so the ORM claims the four Cider models
without touching the database — all tables already exist under their
explicit db_table names (cider_infrastructure, cider_organizations,
cider_features, cider_groups).

The RunPython step updates django_content_type rows from app_label='portal'
to app_label='resources' for these four models. Django's post_migrate signal
then re-anchors auth_permission rows automatically.
"""

from django.db import migrations, models


MODELS_MOVING = [
    'ciderinfrastructure',
    'ciderorganizations',
    'ciderfeatures',
    'cidergroups',
]


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db = schema_editor.connection.alias
    for model_name in MODELS_MOVING:
        ContentType.objects.using(db).filter(
            app_label='portal',
            model=model_name,
        ).update(app_label='resources')


def reverse_update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db = schema_editor.connection.alias
    for model_name in MODELS_MOVING:
        ContentType.objects.using(db).filter(
            app_label='resources',
            model=model_name,
        ).update(app_label='portal')


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0017_delete_focusareasection'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='CiderInfrastructure',
                    fields=[
                        ('cider_resource_id', models.IntegerField(primary_key=True, serialize=False)),
                        ('cider_type', models.CharField(max_length=16)),
                        ('info_resourceid', models.CharField(db_index=True, max_length=40)),
                        ('info_siteid', models.CharField(db_index=True, max_length=40)),
                        ('resource_descriptive_name', models.CharField(max_length=120)),
                        ('resource_description', models.CharField(blank=True, max_length=4000, null=True)),
                        ('resource_status', models.JSONField(blank=True, null=True)),
                        ('current_statuses', models.CharField(blank=True, max_length=64)),
                        ('latest_status', models.CharField(blank=True, max_length=32, null=True)),
                        ('latest_status_begin', models.DateField(blank=True, null=True)),
                        ('latest_status_end', models.DateField(blank=True, null=True)),
                        ('parent_resource', models.IntegerField(blank=True, db_index=True, null=True)),
                        ('recommended_use', models.CharField(blank=True, max_length=4000, null=True)),
                        ('access_description', models.CharField(blank=True, max_length=4000, null=True)),
                        ('project_affiliation', models.CharField(blank=True, max_length=64, null=True)),
                        ('provider_level', models.CharField(blank=True, max_length=16, null=True)),
                        ('protected_attributes', models.JSONField(blank=True, null=True)),
                        ('other_attributes', models.JSONField(blank=True, null=True)),
                        ('updated_at', models.DateTimeField(blank=True, null=True)),
                    ],
                    options={
                        'verbose_name': 'CIDER Infrastructure',
                        'verbose_name_plural': 'CIDER Infrastructure',
                        'db_table': 'cider_infrastructure',
                        'ordering': ['resource_descriptive_name'],
                    },
                ),
                migrations.CreateModel(
                    name='CiderOrganizations',
                    fields=[
                        ('organization_id', models.IntegerField(primary_key=True, serialize=False)),
                        ('organization_name', models.CharField(max_length=120)),
                        ('organization_abbrev', models.CharField(blank=True, max_length=20)),
                        ('organization_url', models.CharField(blank=True, max_length=320, null=True)),
                        ('other_attributes', models.JSONField(blank=True, null=True)),
                    ],
                    options={
                        'verbose_name': 'CIDER Organization',
                        'verbose_name_plural': 'CIDER Organizations',
                        'db_table': 'cider_organizations',
                        'ordering': ['organization_name'],
                    },
                ),
                migrations.CreateModel(
                    name='CiderFeatures',
                    fields=[
                        ('feature_category_id', models.IntegerField(primary_key=True, serialize=False)),
                        ('feature_category_name', models.CharField(max_length=120)),
                        ('feature_category_description', models.CharField(blank=True, max_length=4000, null=True)),
                        ('feature_category_types', models.JSONField(blank=True, null=True)),
                        ('features', models.JSONField(blank=True, null=True)),
                        ('other_attributes', models.JSONField(blank=True, null=True)),
                    ],
                    options={
                        'verbose_name': 'CIDER Feature Category',
                        'verbose_name_plural': 'CIDER Feature Categories',
                        'db_table': 'cider_features',
                        'ordering': ['feature_category_name'],
                    },
                ),
                migrations.CreateModel(
                    name='CiderGroups',
                    fields=[
                        ('group_id', models.IntegerField(primary_key=True, serialize=False)),
                        ('info_groupid', models.CharField(db_index=True, max_length=40, unique=True)),
                        ('group_descriptive_name', models.CharField(max_length=120)),
                        ('group_description', models.CharField(blank=True, max_length=4000, null=True)),
                        ('group_logo_url', models.CharField(blank=True, max_length=320, null=True)),
                        ('group_types', models.JSONField(blank=True, null=True)),
                        ('info_resourceids', models.JSONField(blank=True, null=True)),
                        ('other_attributes', models.JSONField(blank=True, null=True)),
                    ],
                    options={
                        'verbose_name': 'CIDER Group',
                        'verbose_name_plural': 'CIDER Groups',
                        'db_table': 'cider_groups',
                        'ordering': ['group_descriptive_name'],
                        'permissions': [
                            ('rp_coordinator', 'Can coordinate resource provider activities'),
                            ('rp_implementer', 'Can implement resource provider tasks'),
                        ],
                    },
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(
            update_content_types,
            reverse_code=reverse_update_content_types,
        ),
    ]
