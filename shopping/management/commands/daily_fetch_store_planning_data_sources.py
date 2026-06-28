import os

from django.core.management.base import BaseCommand
from django.core.management.base import CommandError

from shopping.domain.dataprovider.public_dataset import PublicDatasetClient
from shopping.domain.service.store_planning_data import StorePlanningDataSourceService


class Command(BaseCommand):
    help = "Fetch public data source metadata for shopping store planning reports"

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and parse data source metadata without writing snapshots.",
        )

    def handle(self, *args, **options):
        estat_app_id = os.getenv("ESTAT_APP_ID")
        if not estat_app_id:
            raise CommandError("ESTAT_APP_ID is not set.")

        client = PublicDatasetClient()
        data_sources = StorePlanningDataSourceService.fetch_all(
            client=client,
            estat_app_id=estat_app_id,
            dry_run=options["dry_run"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Store planning data source fetch completed. "
                f"count={len(data_sources)}, dry_run={options['dry_run']}"
            )
        )
