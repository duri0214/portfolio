from pathlib import Path

import pandas as pd
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils.timezone import now

from securities.domain.valueobject.edinet import EDINET_CODE_LIST_SOURCE_NAME
from securities.models import Company


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
        # The existing company master is replaced only after the CSV structure is validated.

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
        fiscal_year_column = "決算日"
        required_columns = [
            "ＥＤＩＮＥＴコード",
            "提出者種別",
            "上場区分",
            "連結の有無",
            "資本金",
            fiscal_year_column,
            "提出者名",
            "提出者名（英字）",
            "提出者名（ヨミ）",
            "所在地",
            "提出者業種",
            "証券コード",
            "提出者法人番号",
        ]
        missing_columns = [
            column for column in required_columns if column not in df.columns
        ]
        if fiscal_year_column in missing_columns:
            raise CommandError(
                "EDINETコードリストに決算日がありません。"
                "公式のEDINETコードリストをダウンロードして再度取り込んでください。"
            )
        if missing_columns:
            raise CommandError(
                "EDINETコードリストに必要な列がありません: "
                f"{', '.join(missing_columns)}"
            )

        imported_at = now()
        edinet_list = []
        for _, row in df.iterrows():
            end_fiscal_year = na(row[fiscal_year_column])
            edinet_list.append(
                Company(
                    edinet_code=na(row["ＥＤＩＮＥＴコード"]),
                    type_of_submitter=na(row["提出者種別"]),
                    listing_status=na(row["上場区分"]),
                    consolidated_status=na(row["連結の有無"]),
                    capital=(int(row["資本金"]) if pd.notna(row["資本金"]) else None),
                    end_fiscal_year=end_fiscal_year,
                    fiscal_year_end_source=(
                        EDINET_CODE_LIST_SOURCE_NAME
                        if end_fiscal_year is not None
                        else None
                    ),
                    fiscal_year_end_checked_at=(
                        imported_at if end_fiscal_year is not None else None
                    ),
                    submitter_name=na(row["提出者名"]),
                    submitter_name_en=na(row["提出者名（英字）"]),
                    submitter_name_kana=na(row["提出者名（ヨミ）"]),
                    address=na(row["所在地"]),
                    submitter_industry=na(row["提出者業種"]),
                    securities_code=na(row["証券コード"]),
                    corporate_number=na(row["提出者法人番号"]),
                )
            )
        with transaction.atomic():
            Company.objects.all().delete()
            Company.objects.bulk_create(edinet_list)

        self.stdout.write(
            self.style.SUCCESS("Successfully imported all edinet code from CSV")
        )
