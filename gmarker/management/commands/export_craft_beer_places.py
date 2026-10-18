"""クラフトビール候補を Google Places API から出力する管理コマンド。"""

import os

from django.core.management.base import BaseCommand, CommandError

from gmarker.domain.service.craft_beer_places import (
    CraftBeerPlacesExporter,
    PlacesApiClient,
    PlacesApiError,
    RequiredPlaceMissingError,
    load_config,
    write_output,
)


class Command(BaseCommand):
    """設定済みの対象地域について、掲載前検品用の店舗候補を出力する。"""

    help = "Places API からクラフトビール候補を JSON または CSV へ出力します"

    def add_arguments(self, parser):
        parser.add_argument(
            "--config", required=True, help="検索条件を記載した JSON 設定ファイル"
        )
        parser.add_argument(
            "--format", required=True, choices=("json", "csv"), help="出力形式"
        )
        parser.add_argument("--output", required=True, help="出力ファイルのパス")

    def handle(self, *args, **options):
        """設定検証、API抽出、必須候補照合、ファイル出力を順に実行する。"""
        api_key = os.getenv("GOOGLE_MAPS_BE_API_KEY")
        if not api_key:
            raise CommandError("GOOGLE_MAPS_BE_API_KEY を設定してください。")

        try:
            config = load_config(options["config"])
            result = CraftBeerPlacesExporter(PlacesApiClient(api_key)).collect(config)
            write_output(
                result=result,
                output_path=options["output"],
                output_format=options["format"],
            )
        except (ValueError, PlacesApiError, RequiredPlaceMissingError) as error:
            raise CommandError(str(error)) from error

        self.stdout.write(
            self.style.SUCCESS(
                "候補を出力しました: "
                f"候補 {result['counts']['candidates']} 件 / "
                f"手動確認 {result['counts']['manual_review']} 件 / "
                f"除外 {result['counts']['excluded']} 件"
            )
        )
