from django.db import migrations


def migrate_stale_status_values(apps, schema_editor):
    """
    Map any leftover pending_review/approved/rejected rows to draft.

    The submit-for-review workflow was removed in the previous migration, which
    only updates the status field's choices metadata - it does not touch
    existing rows. Any record still holding one of the removed values would
    otherwise silently disappear from the public feed (which filters on
    status='published') without becoming a valid draft an author can act on.
    """
    IntegrationNews = apps.get_model('integration_news', 'IntegrationNews')
    IntegrationNews.objects.filter(
        status__in=['pending_review', 'approved', 'rejected']
    ).update(status='draft')


def noop_reverse(apps, schema_editor):
    # The prior values are not recoverable and the forwards migration is safe
    # to leave applied; nothing to reverse.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('integration_news', '0007_alter_integrationnews_options_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_stale_status_values, noop_reverse),
    ]
