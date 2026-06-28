from django.core.management.base import BaseCommand

from shopping.domain.dataprovider.estat import EstatCsvClient
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
        client = EstatCsvClient()
        data_sources = StorePlanningDataSourceService.fetch_all(
            client=client,
            dry_run=options["dry_run"],
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Store planning data source fetch completed. "
                f"count={len(data_sources)}, dry_run={options['dry_run']}"
            )
        )
