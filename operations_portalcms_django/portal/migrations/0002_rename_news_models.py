# Generated migration for renaming news models

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0001_initial'),
    ]

    operations = [
        migrations.RenameModel(
            old_name='SystemNews',
            new_name='SystemStatusNews',
        ),
        migrations.RenameModel(
            old_name='ResourceNews',
            new_name='IntegrationNews',
        ),
    ]
