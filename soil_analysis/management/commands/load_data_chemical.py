from django.core.management.base import BaseCommand

from soil_analysis.domain.service.management.chemical_import_service import (
    ChemicalImportService,
)


class Command(BaseCommand):
    """川田研究所フォーマットのExcelから化学分析データを取り込むDjangoコマンド

    川田研究所が提供する化学分析結果Excel(.xlsx)を読み込み、
    指定されたLandLedgerに紐づけてSoilChemicalMeasurementテーブルにデータを一括登録する。

    使用方法:
        python manage.py load_data_chemical <excel_path> --land-ledger-id=<id>

    引数:
        excel_path: 川田研究所のExcelファイルパス（.xlsx）
        --land-ledger-id: 取り込み先のLandLedger ID（必須）
        既存データは常に更新されます（upsert）。
    """

    help = "Import chemical analysis data from Excel (Kawada format)"

    def add_arguments(self, parser):
        parser.add_argument("file_path", type=str, help="Path to Excel file (.xlsx)")
        parser.add_argument(
            "--land-ledger-id",
            type=int,
            required=True,
            help="LandLedger ID to associate",
        )

    def handle(self, *args, **options):
        file_path = options["file_path"]
        land_ledger_id = options["land_ledger_id"]

        try:
            result = ChemicalImportService.import_from_excel(file_path, land_ledger_id)

            if "warning" in result:
                self.stdout.write(self.style.WARNING(result["warning"]))
                return

            self.stdout.write(
                self.style.SUCCESS(
                    f"取り込み完了: 新規作成={result['created']}, 更新={result['updated']}, 警告=0"
                )
            )

        except Exception as e:
            self.stderr.write(self.style.ERROR(f"エラー: {str(e)}"))
