"""
Remove the 9 models that have been claimed by resources, infrastructure_news,
and integration_news from portal's ORM state.

SeparateDatabaseAndState with empty database_operations means no DDL is
issued — tables stay exactly as they are.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0017_delete_focusareasection'),
        ('resources', '0001_initial'),
        ('infrastructure_news', '0001_initial'),
        ('integration_news', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.DeleteModel(name='CiderInfrastructure'),
                migrations.DeleteModel(name='CiderOrganizations'),
                migrations.DeleteModel(name='CiderFeatures'),
                migrations.DeleteModel(name='CiderGroups'),
                migrations.DeleteModel(name='SystemStatusNews'),
                migrations.DeleteModel(name='SystemStatusNewsItemPlugin'),
                migrations.DeleteModel(name='IntegrationNews'),
                migrations.DeleteModel(name='IntegrationNewsItemPlugin'),
                migrations.DeleteModel(name='IntegrationElement'),
            ],
            database_operations=[],
        ),
    ]
