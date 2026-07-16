"""
Add is_active to CiderInfrastructure.

Uses SeparateDatabaseAndState because the cider_infrastructure table already
exists in production with no is_active column. The database_operations adds
the column directly so Django does not try to recreate the table.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('resources', '0001_initial'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            state_operations=[
                migrations.AddField(
                    model_name='ciderinfrastructure',
                    name='is_active',
                    field=models.BooleanField(
                        db_index=True,
                        default=True,
                        help_text=(
                            'False when the resource is no longer present in the Warehouse API. '
                            'Inactive rows are retained so historical news relationships remain readable.'
                        ),
                    ),
                ),
            ],
            database_operations=[
                migrations.RunSQL(
                    sql='ALTER TABLE cider_infrastructure ADD COLUMN IF NOT EXISTS is_active boolean NOT NULL DEFAULT true;',
                    reverse_sql='ALTER TABLE cider_infrastructure DROP COLUMN IF EXISTS is_active;',
                ),
                migrations.RunSQL(
                    sql='CREATE INDEX IF NOT EXISTS resources_ciderinfrastructure_is_active ON cider_infrastructure (is_active);',
                    reverse_sql='DROP INDEX IF EXISTS resources_ciderinfrastructure_is_active;',
                ),
            ],
        ),
    ]
