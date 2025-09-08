import os

from django.core.management.base import BaseCommand

from soil_analysis.domain.service.management.commands.soil_hardness_plotter import (
    SoilHardnessPlotterService,
)
from soil_analysis.models import SoilHardnessMeasurement


class Command(BaseCommand):
    help = "土壌硬度測定データから3D表面プロットを生成"

    def add_arguments(self, parser):
        parser.add_argument("--output_dir", type=str, help="出力ディレクトリ")
        parser.add_argument("--land_ledger_id", type=int, help="特定の圃場台帳ID")

    def handle(self, *args, **options):
        # 出力ディレクトリ設定
        output_dir = options["output_dir"] or os.path.join(
            os.path.dirname(os.path.abspath(__file__)), "output"
        )
        os.makedirs(output_dir, exist_ok=True)
        self.stdout.write(f"出力先: {output_dir}")

        # データチェック
        total = SoilHardnessMeasurement.objects.count()
        assigned = SoilHardnessMeasurement.objects.filter(
            land_ledger__isnull=False
        ).count()

        self.stdout.write(f"データ: {assigned}/{total}件が割当済み")

        if assigned == 0:
            self.stdout.write(self.style.ERROR("処理中断: 割当済みデータがありません"))
            return

        # TODO: issue#359 - フォルダベースの処理をland_ledger_idベースに変更してKISS原則に従う
        # フォルダ取得
        folders_queryset = SoilHardnessMeasurement.objects.filter(
            land_ledger__isnull=False
        )
        if options["land_ledger_id"]:
            folders_queryset = folders_queryset.filter(
                land_ledger_id=options["land_ledger_id"]
            )

        folders = [
            f
            for f in folders_queryset.values_list("folder", flat=True).distinct()
            if f and f.strip()
        ]

        self.stdout.write(f"画像化する圃場数: {len(folders)}")

        # データ数の内訳を計算して表示
        if len(folders) > 0:
            data_per_field = assigned // len(folders)  # 1圃場あたりのデータ数
            blocks_per_field = 5  # 5ブロック想定
            measurements_per_block = 5  # 各ブロック5回計測想定
            total_measurements_per_field = blocks_per_field * measurements_per_block
            depth_data_count = (
                data_per_field // total_measurements_per_field
                if total_measurements_per_field > 0
                else 0
            )

            self.stdout.write(
                f"データ内訳: {assigned:,} ÷ {len(folders)} = {data_per_field:,}(1圃場あたり) "
                f"÷ {total_measurements_per_field}({blocks_per_field}ブロック×各{measurements_per_block}回計測) = "
                f"{depth_data_count}(深度データ数)"
            )

        # プロット作成
        plotter = SoilHardnessPlotterService(output_dir=output_dir)
        for folder in folders:
            plotter.plot_3d_surface(
                land_ledger_id=options["land_ledger_id"], folder=folder
            )

        self.stdout.write(self.style.SUCCESS("完了"))
