from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from securities.models import Edinet


class Command(BaseCommand):
    help = "Import edinet code upload from CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_path", type=str, help="Folder path containing CSV file"
        )

    def handle(self, *args, **options):
        # TODO: 決算日は 5月31日 のように入っている
        folder_path = options["folder_path"]
        filename = "EdinetcodeDlInfo.csv"
        file_path = Path(folder_path) / filename
        if not file_path.exists():
            self.stderr.write(self.style.ERROR(f"File does not exist: {file_path}"))
            return
        Edinet.objects.all().delete()

        # Note: 最初の行には `ダウンロード実行日,2024年05月25日現在,件数,10827件` のようなメタデータが入っている
        df = pd.read_csv(
            file_path,
            skiprows=1,
            encoding="cp932",
            dtype={
                "連結の有無": str,
                "決算日": str,
                "証券コード": str,
                "提出者法人番号": str,
            },
        )  # Skip the meta row
        df["資本金"] = (
            df["資本金"].fillna(0).astype(str).str.replace(",", "").astype(float)
        )
        df["連結の有無"] = df["連結の有無"].fillna("").replace("", "無")

        # 3行目以降のデータを保存
        for index, row in df.iterrows():
            Edinet.objects.create(
                edinet_code=row["ＥＤＩＮＥＴコード"],
                type_of_submitter=row["提出者種別"],
                listing_status=row["上場区分"],
                consolidated_status=row["連結の有無"],
                capital=row["資本金"],
                end_fiscal_year=row["決算日"],
                submitter_name=row["提出者名"],
                submitter_name_en=row["提出者名（英字）"],
                submitter_name_kana=row["提出者名（ヨミ）"],
                address=row["所在地"],
                submitter_industry=row["提出者業種"],
                securities_code=row["証券コード"],
                corporate_number=row["提出者法人番号"],
            )

        self.stdout.write(
            self.style.SUCCESS(
                "Successfully imported all edinet master from XBRL files."
            )
        )
