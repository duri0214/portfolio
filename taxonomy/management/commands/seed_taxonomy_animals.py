from django.core.management.base import BaseCommand
from django.db import transaction

from taxonomy.data.animal_taxonomy_seed import ANIMAL_TAXONOMY_SEED
from taxonomy.models import (
    Breed,
    Classification,
    Family,
    Genus,
    Kingdom,
    Phylum,
    Species,
)


class Command(BaseCommand):
    help = "LLMで生成してGit管理した動物分類候補をtaxonomyへ投入します"

    @transaction.atomic
    def handle(self, *args, **options):
        created_count = 0

        for row in ANIMAL_TAXONOMY_SEED:
            kingdom = self._get_or_create(Kingdom, row["kingdom"])
            phylum = self._get_or_create(Phylum, row["phylum"], kingdom=kingdom)
            classification = self._get_or_create(
                Classification, row["classification"], phylum=phylum
            )
            family = self._get_or_create(
                Family, row["family"], classification=classification
            )
            genus = self._get_or_create(Genus, row["genus"], family=family)
            species = self._get_or_create(Species, row["species"], genus=genus)

            for name, name_kana, remark in row["breeds"]:
                _, created = Breed.objects.get_or_create(
                    species=species,
                    name=name,
                    defaults={
                        "name_kana": name_kana,
                        "remark": remark,
                        "natural_monument": None,
                    },
                )
                created_count += int(created)

        self.stdout.write(
            self.style.SUCCESS(
                f"taxonomy animal seed completed: {created_count} breeds"
            )
        )

    def _get_or_create(self, model, data: tuple[str, ...], **parents):
        name, name_en, *remarks = data
        obj, _ = model.objects.get_or_create(
            **parents,
            name=name,
            defaults={"name_en": name_en, "remark": remarks[0] if remarks else None},
        )
        return obj
