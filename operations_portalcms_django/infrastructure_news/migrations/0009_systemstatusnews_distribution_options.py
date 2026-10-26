from django.db import migrations, models


def copy_legacy_distribution_options(apps, schema_editor):
    """Backfill the exact distribution string the pre-migration API exposed.

    A nonempty email_list previously took precedence over send_email, while the
    Slack flag was independent. The legacy fields remain untouched because they
    represent delivery controls rather than the newly persisted publishing intent.
    """

    SystemStatusNews = apps.get_model("infrastructure_news", "SystemStatusNews")
    database = schema_editor.connection.alias
    rows = SystemStatusNews.objects.using(database)
    rows.filter(send_email=True, email_list="").update(distribution_email_everyone=True)
    rows.exclude(email_list="").update(distribution_email_subscribers=True)
    rows.filter(post_to_slack=True).update(distribution_post_to_slack=True)


class Migration(migrations.Migration):
    dependencies = [
        ("infrastructure_news", "0008_migrate_stale_status_values"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemstatusnews",
            name="distribution_email_everyone",
            field=models.BooleanField(default=False, verbose_name="Email everyone with access"),
        ),
        migrations.AddField(
            model_name="systemstatusnews",
            name="distribution_email_subscribers",
            field=models.BooleanField(default=False, verbose_name="Email only subscribers"),
        ),
        migrations.AddField(
            model_name="systemstatusnews",
            name="distribution_post_to_slack",
            field=models.BooleanField(default=False, verbose_name="Post to Slack"),
        ),
        migrations.RunPython(copy_legacy_distribution_options, migrations.RunPython.noop),
    ]
