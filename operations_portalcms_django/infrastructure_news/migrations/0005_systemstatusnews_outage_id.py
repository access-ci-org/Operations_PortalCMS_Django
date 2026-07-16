from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('infrastructure_news', '0004_alter_systemstatusnews_end_datetime_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='systemstatusnews',
            name='outage_id',
            field=models.PositiveIntegerField(
                blank=True,
                db_index=True,
                help_text='Stable external identifier used by API consumers. Carried from Drupal for imported records; auto-assigned for new records.',
                null=True,
                unique=True,
                verbose_name='Outage ID',
            ),
        ),
    ]
