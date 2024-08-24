import csv
import glob
import os
from datetime import datetime

import pytz
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from soil_analysis.models import (
    SoilHardnessMeasurement,
    SoilHardnessMeasurementImportErrors,
    Device,
)


def extract_device(line: list) -> str:
    value = line[1].strip()
    if value != "Digital Cone Penetrometer":
        raise ValueError(f"unexpected data row: {value}")

    value = line[0].strip()
    if not value.startswith("DIK-"):
        raise ValueError(f"unexpected device name: {value}")

    return value


def extract_datetime(line: list) -> datetime:
    value = line[0].strip()
    if value != "Date and Time":
        raise ValueError(f"unexpected data row: {value}")

    value = line[1].strip()
    try:
        value = pytz.timezone("Asia/Tokyo").localize(
            datetime.strptime(value, "%y.%m.%d %H:%M:%S")
        )
    except ValueError:
        raise ValueError(f"unexpected datetime: {value}")

    return value


def extract_numeric_value(line: list) -> int:
    value = line[0].strip()
    if not any(
        value.startswith(prefix)
        for prefix in ("Memory No.", "Set Depth", "Spring", "Cone")
    ):
        raise ValueError(f"unexpected data row: {value}")

    value = line[1].strip()
    try:
        value = int(value)
    except ValueError:
        raise ValueError(f"unexpected numeric value: {value}")
    return value


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
        m_device = {device.name: device for device in Device.objects.all()}

        for csv_file in csv_files:
            parent_folder = os.path.basename(os.path.dirname(csv_file))

            try:
                with open(csv_file, newline="", encoding="utf-8") as f:
                    reader = csv.reader(f)

                    # 1行目～10行目 から属性情報を取得
                    set_device = m_device[extract_device(next(reader))]
                    set_memory = extract_numeric_value(next(reader))
                    next(reader)  # skip Latitude
                    next(reader)  # skip Longitude
                    set_depth = extract_numeric_value(next(reader))
                    set_datetime = extract_datetime(next(reader))
                    set_spring = extract_numeric_value(next(reader))
                    set_cone = extract_numeric_value(next(reader))
                    next(reader)  # skip blank line
                    next(reader)  # skip header line

                    # 11行目以降のデータを保存
                    for row in reader:
                        SoilHardnessMeasurement.objects.create(
                            set_device=set_device,
                            set_memory=set_memory,
                            set_datetime=set_datetime,
                            set_depth=set_depth,
                            set_spring=set_spring,
                            set_cone=set_cone,
                            depth=int(row[0]),
                            pressure=int(row[1]),
                            folder=parent_folder,
                        )

            except IntegrityError as e:
                if "duplicate entry" in str(e).lower():
                    SoilHardnessMeasurementImportErrors.objects.create(
                        file=os.path.basename(csv_file),
                        folder=parent_folder,
                        message="取り込み済み",
                    )
                    self.stderr.write(
                        self.style.WARNING(
                            f"Duplicate entry detected: {parent_folder}/{os.path.basename(csv_file)}. "
                            f"Skipping import."
                        )
                    )
                else:
                    raise e

            except Exception as e:
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
