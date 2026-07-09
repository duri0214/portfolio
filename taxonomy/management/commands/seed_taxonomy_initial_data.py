from django.apps import apps
from django.core.management.base import BaseCommand
from django.db import transaction

from taxonomy.data.initial_seed import INITIAL_TAXONOMY_SEED


class Command(BaseCommand):
    help = "Git管理したTaxonomy初期データをfixtureなしで投入します"

    @transaction.atomic
    def handle(self, *args, **options):
        saved_count = 0

        for row in INITIAL_TAXONOMY_SEED:
            model = apps.get_model(row["model"])
            fields = row["fields"].copy()
            pk = row.get("pk") or fields.pop("id", None)

            defaults = self._build_defaults(model, fields)
            model.objects.update_or_create(pk=pk, defaults=defaults)
            saved_count += 1

        self.stdout.write(
            self.style.SUCCESS(
                f"taxonomy initial seed completed: {saved_count} records"
            )
        )

    def _build_defaults(self, model, fields):
        defaults = {}

        for field in model._meta.fields:
            if field.primary_key:
                continue

            if field.name in fields:
                value = fields[field.name]
            elif field.attname in fields:
                value = fields[field.attname]
            else:
                continue

            if field.is_relation:
                defaults[field.attname] = value
            else:
                defaults[field.name] = value

        return defaults
