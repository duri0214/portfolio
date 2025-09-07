import os

from django.core.management.base import BaseCommand

from soil_analysis.domain.service.soil_hardness_plotter import (
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

        # データチェック
        total = SoilHardnessMeasurement.objects.count()
        assigned = SoilHardnessMeasurement.objects.filter(
            land_ledger__isnull=False
        ).count()

        self.stdout.write(f"データ: {assigned}/{total}件が割当済み")

        if assigned == 0:
            self.stdout.write(self.style.ERROR("処理中断: 割当済みデータがありません"))
            return

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

        # プロット作成
        plotter = SoilHardnessPlotterService(output_dir=output_dir)
        for folder in folders:
            plotter.plot_3d_surface(
                land_ledger_id=options["land_ledger_id"], folder=folder
            )

        self.stdout.write(self.style.SUCCESS("完了"))
