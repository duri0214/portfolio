from django.db import migrations


def seed_no_data_store_planning_target_store(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.update_or_create(
        slug="sapporo-clock-tower",
        defaults={
            "name": "札幌市時計台（データなし表示点検用サンプル）",
            "address": "〒060-0001 北海道札幌市中央区北１条西２丁目",
            "latitude": 43.062563,
            "longitude": 141.353685,
            "city_code": "01101",
            "town_code": "790102",
            "population_area": "北海道札幌市中央区北一条西二丁目",
            "large_area_name": "北一条西",
            "small_area_name": "二丁目",
            "area_hierarchy_level": "4",
            "is_active": True,
        },
    )


def remove_no_data_store_planning_target_store(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    StorePlanningTargetStore.objects.filter(slug="sapporo-clock-tower").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0008_fix_okei_taproom_city_code"),
    ]

    operations = [
        migrations.RunPython(
            seed_no_data_store_planning_target_store,
            remove_no_data_store_planning_target_store,
        ),
    ]
