from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from soil_analysis.domain.service.soil_map_import import (
    SoilMapImportError,
    SoilMapImportService,
)


class Command(BaseCommand):
    """指定した全国土壌図ZIPを検証し、有効版として取り込む。"""

    help = "全国20万分の1土壌図のShape ZIPを取り込み、日本地図の有効版を切り替えます。"

    def add_arguments(self, parser):
        """取込対象のローカルZIPパスを受け取る。"""
        parser.add_argument("zip_path", help="全国20万分の1土壌図のZIPパス")

    def handle(self, *args, **options):
        """ZIPを取り込み、結果を標準出力へ表示する。"""
        zip_path = Path(options["zip_path"])
        if not zip_path.is_file():
            raise CommandError(f"ZIPファイルが見つかりません: {zip_path}")
        try:
            dataset = SoilMapImportService.import_soil_map_from_zip(zip_path)
        except SoilMapImportError as error:
            raise CommandError(str(error)) from error
        self.stdout.write(
            self.style.SUCCESS(
                f"{dataset.feature_count:,}件を取り込みました: {dataset.source_file_name}"
            )
        )
