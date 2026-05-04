from django.db import migrations, models


def copy_owner_group_to_owner_groups(apps, schema_editor):
    FocusAreaSection = apps.get_model('portal', 'FocusAreaSection')

    for section in FocusAreaSection.objects.exclude(owner_group=None):
        section.owner_groups.add(section.owner_group_id)


class Migration(migrations.Migration):

    dependencies = [
        ('portal', '0013_focusareasection'),
    ]

    operations = [
        migrations.AddField(
            model_name='focusareasection',
            name='owner_groups',
            field=models.ManyToManyField(blank=True, related_name='owned_focus_area_sections', to='auth.group'),
        ),
        migrations.RunPython(copy_owner_group_to_owner_groups, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name='focusareasection',
            name='owner_group',
        ),
    ]
