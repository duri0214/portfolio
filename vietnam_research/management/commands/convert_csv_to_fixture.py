import csv
import json
import os

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    """
    CSV ファイルを Django フィクスチャ JSON 形式に変換します。

    このコマンドは、このスクリプトが配置されているディレクトリ内のすべての CSV ファイルを処理します。
    そしてそれらを Django 用の JSON フィクスチャ ファイルに変換します。 CSV ファイル名によって決まります。
    JSON の「model」フィールド。ファイル名のアンダースコアはドットに置き換えられます。

    Example:
        Given a file `hospital_city.csv` with the content:

            "id","name"
            1,堺市
            2,大阪市
            3,大阪府

        Running the command:

            python manage.py convert_csv_to_fixture

        Will produce a JSON file `hospital_city.json` with the following content:

            [
              {
                "model": "hospital.city",
                "pk": 1,
                "fields": {
                  "name": "堺市"
                }
              },
              {
                "model": "hospital.city",
                "pk": 2,
                "fields": {
                  "name": "大阪市"
                }
              },
              {
                "model": "hospital.city",
                "pk": 3,
                "fields": {
                  "name": "大阪府"
                }
              }
            ]

    Usage:
        Place the CSV files in the same directory as this script and run the command.
        Each CSV file will be converted to a corresponding JSON file.
    """

    help = "Convert CSV files to Django fixture JSON format"

    def handle(self, *args, **options):
        script_dir = os.path.dirname(__file__)  # Get the directory of this script
        csv_files = [f for f in os.listdir(script_dir) if f.endswith(".csv")]

        for csv_file in csv_files:
            model_name = os.path.splitext(csv_file)[0].replace(
                "_", "."
            )  # Convert file name to model name
            output = []

            csv_path = os.path.join(script_dir, csv_file)
            with open(csv_path, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for i, row in enumerate(reader, start=1):
                    output.append(
                        {"model": model_name, "pk": i, "fields": {"name": row["name"]}}
                    )

            json_file = f"{csv_file.replace('.csv', '.json')}"
            json_path = os.path.join(script_dir, json_file)
            with open(json_path, "w", encoding="utf-8") as outfile:
                json.dump(output, outfile, ensure_ascii=False, indent=2)

            self.stdout.write(
                self.style.SUCCESS(f"Processed {csv_file} -> {json_file}")
            )
