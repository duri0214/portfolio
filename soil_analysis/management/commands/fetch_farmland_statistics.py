import os
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from soil_analysis.domain.dataprovider.estat import EstatApiClient
from soil_analysis.domain.service.agricultural_statistics import (
    DEFAULT_AREA_CODE,
    NATIONAL_AREA_CODE,
    AgriculturalStatisticsService,
)


class Command(BaseCommand):
    help = "Fetch e-Stat agricultural statistics for farmland risk reports"

    def add_arguments(self, parser):
        parser.add_argument(
            "--area-code",
            default=DEFAULT_AREA_CODE,
            help="e-Stat area code. Default is the initial target area: 02405.",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Save snapshots even when the source hash already exists.",
        )
        parser.add_argument(
            "--skip-national",
            action="store_true",
            help=f"Fetch only --area-code and skip national area {NATIONAL_AREA_CODE}.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Fetch and parse data without writing snapshots or reports.",
        )
        parser.add_argument(
            "--target-date",
            help="Fallback period label date in YYYY-MM-DD format.",
        )

    def handle(self, *args, **options):
        app_id = os.getenv("ESTAT_APP_ID")
        if not app_id:
            raise CommandError("ESTAT_APP_ID is not set.")

        target_date = self._parse_target_date(options.get("target_date"))
        client = EstatApiClient(app_id)
        result = AgriculturalStatisticsService.fetch_and_store(
            client=client,
            area_code=options["area_code"],
            include_national=not options["skip_national"],
            target_date=target_date,
            force=options["force"],
            dry_run=options["dry_run"],
        )
        if result.skipped_dataset_keys:
            self.stdout.write(
                self.style.WARNING(
                    "Skipped datasets without configured statsDataId: "
                    + ", ".join(result.skipped_dataset_keys)
                )
            )
        fetched_count = (
            result.created_count + result.skipped_count + result.dry_run_count
        )
        if fetched_count == 0 and result.skipped_dataset_keys:
            raise CommandError(
                "No e-Stat datasets were fetched. Configure EstatDataset.stats_data_id "
                "and filters before running this command."
            )
        self.stdout.write(
            self.style.SUCCESS(
                "e-Stat farmland statistics fetch completed. "
                f"created={result.created_count}, "
                f"skipped={result.skipped_count}, "
                f"dry_run={result.dry_run_count}"
            )
        )

    @staticmethod
    def _parse_target_date(value: str | None) -> date | None:
        if not value:
            return None
        try:
            return date.fromisoformat(value)
        except ValueError as error:
            raise CommandError("--target-date must be YYYY-MM-DD.") from error
