import re

from django.db import migrations

PROVENANCE_RE = re.compile(r'^\[drupal_nid:([^;]+);drupal_vid:([^\]]+)\]$')


def clear_backfilled_comments(apps, schema_editor):
    IntegrationNews = apps.get_model('integration_news', 'IntegrationNews')
    for news in IntegrationNews.objects.exclude(drupal_nid__isnull=True).exclude(drupal_nid=''):
        match = PROVENANCE_RE.match(news.review_comments or '')
        if not match:
            continue
        nid, _vid = match.groups()
        if nid != news.drupal_nid:
            continue
        news.review_comments = ''
        news.save(update_fields=['review_comments'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('integration_news', '0006_backfill_drupal_provenance'),
    ]

    operations = [
        migrations.RunPython(clear_backfilled_comments, noop_reverse),
    ]
