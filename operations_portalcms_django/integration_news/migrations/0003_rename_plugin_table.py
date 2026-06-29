from django.db import migrations


class Migration(migrations.Migration):
    """
    The plugin table was created in portal/0004 as portal_integrationnewsitemplugin
    and later renamed outside the migration state to
    operations_portalcms_django_integrationnewsitemplugin. The 0001_initial
    SeparateDatabaseAndState recorded the state as portal_* (the original name), so
    AlterModelTable in 0002 was a no-op. This migration renames the table back to
    portal_integrationnewsitemplugin at the DB level.

    The conditional DO $$ block is safe on both production (where the source table
    existed and was renamed) and a fresh database (where portal/0004 creates it as
    portal_* directly and no rename is needed).
    """

    dependencies = [
        ('integration_news', '0002_rename_to_portal_prefix'),
    ]

    operations = [
        migrations.RunSQL(
            sql="""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_tables
                        WHERE tablename = 'operations_portalcms_django_integrationnewsitemplugin'
                    ) THEN
                        ALTER TABLE operations_portalcms_django_integrationnewsitemplugin
                            RENAME TO portal_integrationnewsitemplugin;
                    END IF;
                END $$;
            """,
            reverse_sql="""
                DO $$ BEGIN
                    IF EXISTS (
                        SELECT 1 FROM pg_tables
                        WHERE tablename = 'portal_integrationnewsitemplugin'
                    ) THEN
                        ALTER TABLE portal_integrationnewsitemplugin
                            RENAME TO operations_portalcms_django_integrationnewsitemplugin;
                    END IF;
                END $$;
            """,
        ),
    ]
