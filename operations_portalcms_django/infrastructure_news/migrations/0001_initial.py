"""
Initial migration for the `infrastructure_news` app.

Uses SeparateDatabaseAndState so the ORM claims SystemStatusNews and
SystemStatusNewsItemPlugin without touching the database — both tables
already exist under their explicit db_table names.

NOTE: SystemStatusNews has a ManyToManyField to CiderInfrastructure
(now in the `resources` app). The M2M through table
(operations_portalcms_django_systemstatusnews_affected_infrastructure_items)
also already exists and is not touched here.

The RunPython step updates django_content_type rows from app_label='portal'
to app_label='infrastructure_news' for these two models.
"""

from django.db import migrations, models
import django.db.models.deletion


MODELS_MOVING = [
    'systemstatusnews',
    'systemstatusnewsitemplugin',
]


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db = schema_editor.connection.alias
    for model_name in MODELS_MOVING:
        ContentType.objects.using(db).filter(
            app_label='portal',
            model=model_name,
        ).update(app_label='infrastructure_news')


def reverse_update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db = schema_editor.connection.alias
    for model_name in MODELS_MOVING:
        ContentType.objects.using(db).filter(
            app_label='infrastructure_news',
            model=model_name,
        ).update(app_label='portal')


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0017_delete_focusareasection'),
        ('resources', '0001_initial'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('cms', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='SystemStatusNews',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('subject', models.CharField(default='Untitled', max_length=200, verbose_name='Subject')),
                        ('content', models.TextField(verbose_name='News Content')),
                        ('infrastructure_news_type', models.CharField(
                            choices=[
                                ('degraded', 'Degraded'),
                                ('introduction', 'Introduction'),
                                ('outage_full', 'Outage Full'),
                                ('outage_partial', 'Outage Partial'),
                                ('reconfiguration', 'Reconfiguration'),
                                ('retirement', 'Retirement'),
                            ],
                            default='outage_full',
                            max_length=50,
                            verbose_name='Infrastructure News Type',
                        )),
                        ('affected_infrastructure', models.CharField(
                            blank=True, max_length=255,
                            verbose_name='Affected Infrastructure',
                            help_text='Resource ID(s) from CIDER (comma-separated if multiple)',
                        )),
                        ('start_datetime', models.DateTimeField(blank=True, null=True, verbose_name='Start Date and Time')),
                        ('end_datetime', models.DateTimeField(blank=True, null=True, verbose_name='End Date and Time')),
                        ('effective_date', models.DateField(blank=True, null=True)),
                        ('expiration_date', models.DateField(blank=True, null=True)),
                        ('send_email', models.BooleanField(default=False, verbose_name='Send Email Notification')),
                        ('email_list', models.CharField(blank=True, max_length=500, verbose_name='Email Recipients')),
                        ('post_to_slack', models.BooleanField(default=False, verbose_name='Post to Slack')),
                        ('slack_channel', models.CharField(blank=True, max_length=100, verbose_name='Slack Channel')),
                        ('created_at', models.DateTimeField(auto_now_add=True)),
                        ('updated_at', models.DateTimeField(auto_now=True)),
                        ('is_active', models.BooleanField(default=True)),
                        ('status', models.CharField(
                            choices=[
                                ('draft', 'Draft'),
                                ('pending_review', 'Pending Review'),
                                ('approved', 'Approved'),
                                ('published', 'Published'),
                                ('rejected', 'Rejected'),
                            ],
                            default='published',
                            max_length=20,
                        )),
                        ('reviewed_at', models.DateTimeField(blank=True, null=True)),
                        ('review_comments', models.TextField(blank=True)),
                        ('published_at', models.DateTimeField(blank=True, null=True)),
                        ('author', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            related_name='authored_systemstatus_news',
                            to='auth.user',
                        )),
                        ('reviewer', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='reviewed_systemstatus_news',
                            to='auth.user',
                        )),
                        ('published_by', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='published_systemstatus_news',
                            to='auth.user',
                        )),
                        ('affected_infrastructure_items', models.ManyToManyField(
                            blank=True,
                            related_name='system_status_news_items',
                            to='resources.ciderinfrastructure',
                            verbose_name='Affected Infrastructure Items',
                        )),
                    ],
                    options={
                        'verbose_name': 'System and Infrastructure Status News',
                        'verbose_name_plural': 'System and Infrastructure Status News',
                        'db_table': 'operations_portalcms_django_systemstatusnews',
                        'ordering': ['-start_datetime'],
                        'permissions': [
                            ('can_review_systemstatusnews', 'Can review System Status News'),
                            ('can_publish_systemstatusnews', 'Can publish System Status News'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='SystemStatusNewsItemPlugin',
                    fields=[
                        ('cmsplugin_ptr', models.OneToOneField(
                            auto_created=True,
                            on_delete=django.db.models.deletion.CASCADE,
                            parent_link=True,
                            primary_key=True,
                            serialize=False,
                            to='cms.cmsplugin',
                        )),
                        ('title', models.CharField(max_length=200)),
                        ('content', models.TextField()),
                        ('published_date', models.DateTimeField(auto_now_add=True)),
                        ('author', models.ForeignKey(
                            on_delete=django.db.models.deletion.CASCADE,
                            to='auth.user',
                        )),
                    ],
                    options={
                        'ordering': ['-published_date'],
                        'db_table': 'portal_systemstatusnewsitemplugin',
                    },
                    bases=('cms.cmsplugin',),
                ),
            ],
            database_operations=[],
        ),
        migrations.RunPython(
            update_content_types,
            reverse_code=reverse_update_content_types,
        ),
    ]
