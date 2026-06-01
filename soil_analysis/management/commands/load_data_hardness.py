import os

from django.core.management.base import BaseCommand

from soil_analysis.domain.service.management.hardness_import_service import (
    HardnessImportService,
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
            result = HardnessImportService.import_from_folder(folder_path)

            for file_result in result["file_results"]:
                if file_result["status"] == "success":
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"Successfully imported {file_result['count']} records from {file_result['file']}"
                        )
                    )
                else:
                    parent_folder = os.path.basename(
                        os.path.dirname(file_result["file"])
                    )
                    file_name = os.path.basename(file_result["file"])
                    self.stderr.write(
                        self.style.ERROR(
                            f"Error occurred while importing soil hardness measurements "
                            f"from {parent_folder}/{file_name}: {file_result['message']}"
                        )
                    )

            self.stdout.write(
                self.style.SUCCESS(
                    "Successfully imported all soil hardness measurements from CSV files."
                )
            )
        except Exception as e:
            self.stderr.write(self.style.ERROR(str(e)))
