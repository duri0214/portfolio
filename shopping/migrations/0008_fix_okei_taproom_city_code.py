from django.db import migrations


def fix_okei_taproom_city_code(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.filter(
        slug="okei-taproom",
        city_code="013113",
    ).update(city_code="13113")


def restore_okei_taproom_city_code(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.filter(
        slug="okei-taproom",
        city_code="13113",
    ).update(city_code="013113")


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0007_seed_store_planning_target_stores"),
    ]

    operations = [
        migrations.RunPython(
            fix_okei_taproom_city_code,
            restore_okei_taproom_city_code,
        ),
    ]
