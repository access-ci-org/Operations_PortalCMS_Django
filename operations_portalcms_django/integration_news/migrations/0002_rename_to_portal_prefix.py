from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('integration_news', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelTable(
            name='integrationelement',
            table='portal_integrationelement',
        ),
        migrations.AlterModelTable(
            name='integrationnews',
            table='portal_integrationnews',
        ),
        migrations.AlterModelTable(
            name='integrationnewsitemplugin',
            table='portal_integrationnewsitemplugin',
        ),
    ]
