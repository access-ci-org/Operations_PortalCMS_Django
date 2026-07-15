import re

from django.db import migrations

PROVENANCE_RE = re.compile(r'^\[drupal_nid:([^;]+);drupal_vid:([^\]]+)\]$')


def backfill_drupal_provenance(apps, schema_editor):
    IntegrationNews = apps.get_model('integration_news', 'IntegrationNews')
    for news in IntegrationNews.objects.filter(review_comments__contains='[drupal_nid:'):
        match = PROVENANCE_RE.match(news.review_comments or '')
        if not match:
            continue
        nid, vid = match.groups()
        news.drupal_nid = nid
        news.drupal_vid = None if vid == 'None' else vid
        news.save(update_fields=['drupal_nid', 'drupal_vid'])


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('integration_news', '0005_integrationnews_drupal_nid_and_more'),
    ]

    operations = [
        migrations.RunPython(backfill_drupal_provenance, noop_reverse),
    ]
