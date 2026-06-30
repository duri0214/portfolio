from django.db import migrations


def fix_sapporo_clock_tower_town_code(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.filter(slug="sapporo-clock-tower").update(
        town_code="790102"
    )


def restore_sapporo_clock_tower_town_code(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.filter(slug="sapporo-clock-tower").update(
        town_code="999999"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0009_seed_no_data_store_planning_target_store"),
    ]

    operations = [
        migrations.RunPython(
            fix_sapporo_clock_tower_town_code,
            restore_sapporo_clock_tower_town_code,
        ),
    ]
