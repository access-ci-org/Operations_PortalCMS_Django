import djangocms_text.fields
from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ('integration_news', '0008_migrate_stale_status_values'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.AlterField(
                    model_name='integrationnews',
                    name='content',
                    field=djangocms_text.fields.HTMLField(),
                ),
            ],
        ),
    ]
