from django.db import migrations


def label_sapporo_clock_tower_sample(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.filter(slug="sapporo-clock-tower").update(
        name="札幌市時計台（データなし表示点検用サンプル）"
    )


def restore_sapporo_clock_tower_name(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.filter(slug="sapporo-clock-tower").update(
        name="札幌市時計台"
    )


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0010_fix_sapporo_clock_tower_town_code"),
    ]

    operations = [
        migrations.RunPython(
            label_sapporo_clock_tower_sample,
            restore_sapporo_clock_tower_name,
        ),
    ]
