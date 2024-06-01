from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand

from securities.models import Edinet


def na(value):
    return value if pd.notna(value) else None


class Command(BaseCommand):
    help = "Import edinet code upload from CSV"

    def add_arguments(self, parser):
        parser.add_argument(
            "folder_path", type=str, help="Folder path containing CSV file"
        )

    def handle(self, *args, **options):
        folder_path = options["folder_path"]
        filename = "EdinetcodeDlInfo.csv"
        file_path = Path(folder_path) / filename
        if not file_path.exists():
            raise FileNotFoundError(f"File does not exist: {file_path}")
        Edinet.objects.all().delete()

        # Note: 最初の行には `ダウンロード実行日...` のようなメタデータが入っているのでskip
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
        )
        # 3行目以降のデータを保存
        edinet_list = []
        for _, row in df.iterrows():
            edinet_list.append(
                Edinet(
                    edinet_code=na(row["ＥＤＩＮＥＴコード"]),
                    type_of_submitter=na(row["提出者種別"]),
                    listing_status=na(row["上場区分"]),
                    consolidated_status=na(row["連結の有無"]),
                    capital=(int(row["資本金"]) if pd.notna(row["資本金"]) else None),
                    end_fiscal_year=na(row["決算日"]),
                    submitter_name=na(row["提出者名"]),
                    submitter_name_en=na(row["提出者名（英字）"]),
                    submitter_name_kana=na(row["提出者名（ヨミ）"]),
                    address=na(row["所在地"]),
                    submitter_industry=na(row["提出者業種"]),
                    securities_code=na(row["証券コード"]),
                    corporate_number=na(row["提出者法人番号"]),
                )
            )
        Edinet.objects.bulk_create(edinet_list)

        self.stdout.write(
            self.style.SUCCESS("Successfully imported all edinet code from CSV")
        )
