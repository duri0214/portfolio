from django.db import migrations
from django.db.models import F


EDINET_CODE_LIST_SOURCE_NAME = "EDINETコードリストの決算日"


def backfill_fiscal_year_traceability(apps, schema_editor):
    Company = apps.get_model("securities", "Company")
    Company.objects.filter(fiscal_year_end_source__isnull=True).update(
        fiscal_year_end_source=EDINET_CODE_LIST_SOURCE_NAME
    )
    Company.objects.filter(fiscal_year_end_checked_at__isnull=True).update(
        fiscal_year_end_checked_at=F("updated_at")
    )


class Migration(migrations.Migration):
    dependencies = [
        ("securities", "0002_company_fiscal_year_end_checked_at_and_more"),
    ]

    operations = [
        migrations.RunPython(
            backfill_fiscal_year_traceability,
            reverse_code=migrations.RunPython.noop,
        ),
    ]
