import csv
import json
import os
from datetime import datetime

from django.core.management.base import BaseCommand
from django.utils.timezone import make_aware


class Command(BaseCommand):
    """
    CSV ファイルを Django フィクスチャ JSON 形式に変換します。

    このコマンドは、このスクリプトが配置されているディレクトリ内のすべての CSV ファイルを処理します。
    そしてそれらを Django 用の JSON フィクスチャ ファイルに変換します。JSON の「model」フィールドは
    CSV ファイル名によって決まります。ファイル名のアンダースコアはドットに置き換えられます。
    CSVファイル名は2つのセクションに分ける必要があります。例えば「hospital_city.csv」のように。

    Usage:
        CSV ファイルをこのスクリプトと同じディレクトリに配置し、コマンドを実行します。
        各 CSV ファイルは、対応する JSON ファイルに変換されます。
    """

    help = "Convert CSV files to Django fixture JSON format"

    def handle(self, *args, **options):
        script_dir = os.path.dirname(__file__)  # Get the directory of this script
        csv_files = [f for f in os.listdir(script_dir) if f.endswith(".csv")]

        for csv_file in csv_files:
            if len(csv_file.split("_")) != 2:
                self.stdout.write(
                    self.style.ERROR(
                        f"Invalid file name {csv_file}. File name should contain exactly one underscore (_)."
                    )
                )
                continue

            model_name = os.path.splitext(csv_file)[0].replace(
                "_", "."
            )  # Convert file name to model name
            output = []

            csv_path = os.path.join(script_dir, csv_file)
            with open(csv_path, "r", encoding="utf-8") as file:
                reader = csv.DictReader(file)
                for i, row in enumerate(reader, start=1):
                    fields_dict = dict(row)
                    fields_dict.pop(
                        "id", None
                    )  # remove 'id' from fields as 'id' is used as 'pk'
                    fields_dict.pop(
                        "created_at", None
                    )  # remove 'created_at' from fields
                    fields_dict.pop(
                        "updated_at", None
                    )  # remove 'updated_at' from fields
                    fields_dict["created_at"] = make_aware(
                        datetime.now()
                    ).isoformat()  # set 'created_at' as the current timestamp
                    output.append({"model": model_name, "pk": i, "fields": fields_dict})

            json_file = f"{csv_file.split('_')[1].replace('.csv', '.json')}"
            json_path = os.path.join(script_dir, json_file)
            with open(json_path, "w", encoding="utf-8") as outfile:
                json.dump(output, outfile, ensure_ascii=False, indent=2)

            self.stdout.write(
                self.style.SUCCESS(f"Processed {csv_file} -> {json_file}")
            )
