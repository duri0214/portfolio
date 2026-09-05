from django.db import migrations


FOIP_DESCRIPTION = (
    "Free and Open Indo-Pacific（自由で開かれたインド太平洋）の略称で、"
    "法の支配に基づく自由で開かれた地域の実現を目指す外交上の概念です。"
)
FOIP_SOURCE_URL = "https://www.meti.go.jp/policy/external_economy/trade/foip/index.html"


def seed_dictionary(apps, schema_editor):
    entry_model = apps.get_model("kokkai", "ReadingSupportEntry")
    entry_model.objects.update_or_create(
        normalized_surface="foip",
        defaults={
            "entry_type": "term",
            "surface": "FOIP",
            "reading": "フォイップ",
            "description": FOIP_DESCRIPTION,
            "category": "政策・略語",
            "source_url": FOIP_SOURCE_URL,
            "is_active": True,
        },
    )
    entry_model.objects.update_or_create(
        normalized_surface="お諮り",
        defaults={
            "entry_type": "reading_override",
            "surface": "お諮り",
            "reading": "おはかり",
            "description": "",
            "category": "",
            "source_url": "",
            "is_active": True,
        },
    )


def remove_seed_dictionary(apps, schema_editor):
    entry_model = apps.get_model("kokkai", "ReadingSupportEntry")
    entry_model.objects.filter(normalized_surface__in=("foip", "お諮り")).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("kokkai", "0020_readingsupportdraft_readingsupportentry_and_more"),
    ]

    operations = [
        migrations.RunPython(seed_dictionary, remove_seed_dictionary),
    ]
