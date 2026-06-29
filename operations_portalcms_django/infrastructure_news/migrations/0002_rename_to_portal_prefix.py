from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('infrastructure_news', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='systemstatusnews',
            table='portal_systemstatusnews',
        ),
        migrations.AlterModelTable(
            name='systemstatusnewsitemplugin',
            table='portal_systemstatusnewsitemplugin',
        ),
    ]
