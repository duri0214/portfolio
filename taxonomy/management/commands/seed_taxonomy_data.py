from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Taxonomyの初期データと追加動物分類候補をまとめて投入します"

    def handle(self, *args, **options):
        call_command("seed_taxonomy_initial_data")
        call_command("seed_taxonomy_animals")
        self.stdout.write(self.style.SUCCESS("taxonomy data seed completed"))
