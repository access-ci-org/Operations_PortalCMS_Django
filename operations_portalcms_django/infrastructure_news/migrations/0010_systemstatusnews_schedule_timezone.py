from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("infrastructure_news", "0009_systemstatusnews_distribution_options"),
    ]

    operations = [
        migrations.AddField(
            model_name="systemstatusnews",
            name="schedule_timezone",
            field=models.CharField(
                default="America/Chicago",
                editable=False,
                help_text="IANA time zone used to enter and display the start and end dates.",
                max_length=64,
                verbose_name="Schedule Time Zone",
            ),
        ),
    ]
