import glob
import os

from django.core.management.base import BaseCommand

from soil_analysis.domain.service.hardness_import_service import HardnessImportService
from soil_analysis.models import (
    SoilHardnessMeasurementImportErrors,
)


class Command(BaseCommand):
    help = "Import soil hardness measurements from CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_path", type=str, help="Folder path containing CSV files"
        )

    def handle(self, *args, **options):
        folder_path = options["folder_path"]
        try:
            if not folder_path or not os.path.exists(folder_path):
                raise ValueError(f"Folder path does not exist: {folder_path}")
        except ValueError as e:
            self.stderr.write(self.style.ERROR(str(e)))
            return

        SoilHardnessMeasurementImportErrors.objects.all().delete()
        csv_files = glob.glob(
            os.path.join(options["folder_path"], "**/*.csv"), recursive=True
        )

        for csv_file in csv_files:
            try:
                rows = HardnessImportService.parse_csv(csv_file)
                result = HardnessImportService.save_import_data(rows)
                if result["created"] > 0:
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully imported {result['created']} records from {csv_file}"
                        )
                    )
            except Exception as e:
                parent_folder = os.path.basename(os.path.dirname(csv_file))
                SoilHardnessMeasurementImportErrors.objects.create(
                    file=os.path.basename(csv_file),
                    folder=parent_folder,
                    message=str(e),
                )
                self.stderr.write(
                    self.style.ERROR(
                        f"Error occurred while importing soil hardness measurements "
                        f"from {parent_folder}/{os.path.basename(csv_file)}: {str(e)}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully imported all soil hardness measurements from CSV files."
            )
        )
