from django.db import migrations


def seed_store_planning_target_stores(apps, schema_editor):
    StorePlanningTargetStore = apps.get_model("shopping", "StorePlanningTargetStore")
    stores = [
        {
            "slug": "chapter-table",
            "name": "Chapter Table",
            "address": "東京都足立区東保木間二丁目",
            "latitude": 35.792822,
            "longitude": 139.8143238,
            "city_code": "13121",
            "town_code": "073002",
            "population_area": "東京都足立区東保木間二丁目",
            "large_area_name": "東保木間",
            "small_area_name": "二丁目",
            "area_hierarchy_level": "4",
            "is_active": True,
        },
        {
            "slug": "okei-taproom",
            "name": "OKEI TAPROOM オケタプ",
            "address": "〒151-0053 東京都渋谷区代々木１丁目５２−４ ベルテ南新宿 地下１階",
            "latitude": 35.683713863354235,
            "longitude": 139.69973314970687,
            "city_code": "013113",
            "town_code": "030001",
            "population_area": "代々木一丁目",
            "large_area_name": "代々木",
            "small_area_name": "一丁目",
            "area_hierarchy_level": "4",
            "is_active": True,
        },
    ]
    for store in stores:
        slug = store.pop("slug")
        StorePlanningTargetStore.objects.update_or_create(
            slug=slug,
            defaults=store,
        )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("shopping", "0006_storeplanningtargetstore"),
    ]

    operations = [
        migrations.RunPython(seed_store_planning_target_stores, noop_reverse),
    ]
