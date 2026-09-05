from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from kokkai.domain.service.reading_support_import import ReadingSupportCsvImporter


class Command(BaseCommand):
    """読み仮名支援辞書CSVを検証・取り込む管理コマンド。"""

    help = "用語・読み補正のCSVを読み仮名支援辞書へ取り込みます。"

    def add_arguments(self, parser):
        parser.add_argument("csv_path", type=Path, help="UTF-8 CSVファイルのパス")
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="同じ正規化表記の既存データを更新する",
        )

    def handle(self, *args, **options):
        csv_path: Path = options["csv_path"]
        if not csv_path.is_file():
            raise CommandError(f"CSVファイルが見つかりません: {csv_path}")
        result = ReadingSupportCsvImporter().import_csv(
            csv_path.read_bytes(),
            update_existing=options["update_existing"],
        )
        if result.errors:
            for error in result.errors:
                self.stderr.write(
                    self.style.ERROR(f"{error.line_number}行目: {error.message}")
                )
            raise CommandError("CSVの検証に失敗したため、取り込みを中止しました。")
        self.stdout.write(
            self.style.SUCCESS(
                "取り込み完了: "
                f"新規={result.created}, 更新={result.updated}, スキップ={result.skipped}"
            )
        )
