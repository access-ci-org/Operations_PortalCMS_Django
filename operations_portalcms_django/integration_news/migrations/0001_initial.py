"""
Initial migration for the `integration_news` app.

Uses SeparateDatabaseAndState so the ORM claims IntegrationNews,
IntegrationNewsItemPlugin, and IntegrationElement without touching
the database — all tables already exist under their explicit db_table names.

The RunPython step updates django_content_type rows from app_label='portal'
to app_label='integration_news' for these three models.
"""

from django.db import migrations, models
import django.db.models.deletion


MODELS_MOVING = [
    'integrationnews',
    'integrationnewsitemplugin',
    'integrationelement',
]


def update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db = schema_editor.connection.alias
    for model_name in MODELS_MOVING:
        ContentType.objects.using(db).filter(
            app_label='portal',
            model=model_name,
        ).update(app_label='integration_news')


def reverse_update_content_types(apps, schema_editor):
    ContentType = apps.get_model('contenttypes', 'ContentType')
    db = schema_editor.connection.alias
    for model_name in MODELS_MOVING:
        ContentType.objects.using(db).filter(
            app_label='integration_news',
            model=model_name,
        ).update(app_label='portal')


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0017_delete_focusareasection'),
        ('contenttypes', '0002_remove_content_type_name'),
        ('cms', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.CreateModel(
                    name='IntegrationElement',
                    fields=[
                        ('code', models.CharField(max_length=100, primary_key=True, serialize=False)),
                        ('label', models.CharField(max_length=200)),
                    ],
                    options={
                        'verbose_name': 'Integration Element',
                        'verbose_name_plural': 'Integration Elements',
                        'db_table': 'operations_portalcms_django_integrationelement',
                        'ordering': ['label'],
                    },
                ),
                migrations.CreateModel(
                    name='IntegrationNews',
                    fields=[
                        ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                        ('title', models.CharField(max_length=200)),
                        ('content', models.TextField()),
                        ('news_type', models.CharField(blank=True, max_length=50)),
                        ('affected_element', models.CharField(blank=True, max_length=100)),
                        ('effective_date', models.DateField(blank=True, null=True)),
                        ('expiration_date', models.DateField(blank=True, null=True)),
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
                            related_name='authored_integration_news',
                            to='auth.user',
                        )),
                        ('reviewer', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='reviewed_integration_news',
                            to='auth.user',
                        )),
                        ('published_by', models.ForeignKey(
                            blank=True, null=True,
                            on_delete=django.db.models.deletion.SET_NULL,
                            related_name='published_integration_news',
                            to='auth.user',
                        )),
                        ('affected_elements', models.ManyToManyField(
                            blank=True,
                            related_name='integration_news_items',
                            to='integration_news.integrationelement',
                            verbose_name='Affected Elements',
                        )),
                    ],
                    options={
                        'verbose_name': 'Integration News',
                        'verbose_name_plural': 'Integration News',
                        'db_table': 'operations_portalcms_django_integrationnews',
                        'ordering': ['-created_at'],
                        'permissions': [
                            ('can_review_integrationnews', 'Can review Integration News'),
                            ('can_publish_integrationnews', 'Can publish Integration News'),
                        ],
                    },
                ),
                migrations.CreateModel(
                    name='IntegrationNewsItemPlugin',
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
                        'db_table': 'portal_integrationnewsitemplugin',
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
