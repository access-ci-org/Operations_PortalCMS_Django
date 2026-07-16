from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('integration_news', '0004_alter_integrationnews_review_comments_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='integrationnews',
            name='integration_news_id',
            field=models.PositiveIntegerField(
                blank=True,
                db_index=True,
                help_text='Stable external identifier used by API consumers. Carried from Drupal for imported records; auto-assigned for new records.',
                null=True,
                unique=True,
                verbose_name='Integration News ID',
            ),
        ),
    ]
