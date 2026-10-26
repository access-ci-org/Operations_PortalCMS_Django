from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("integration_news", "0008_migrate_stale_status_values"),
    ]

    operations = [
        migrations.AddField(
            model_name="integrationnews",
            name="distribution_email_everyone",
            field=models.BooleanField(default=False, verbose_name="Email everyone with access"),
        ),
        migrations.AddField(
            model_name="integrationnews",
            name="distribution_email_subscribers",
            field=models.BooleanField(default=False, verbose_name="Email only subscribers"),
        ),
        migrations.AddField(
            model_name="integrationnews",
            name="distribution_post_to_slack",
            field=models.BooleanField(default=False, verbose_name="Post to Slack"),
        ),
    ]
