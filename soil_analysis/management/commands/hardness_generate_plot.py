import os

from django.core.management.base import BaseCommand

from soil_analysis.domain.service.management.commands.soil_hardness_plotter import (
    SoilHardnessPlotterService,
)
from soil_analysis.models import SoilHardnessMeasurement


class Command(BaseCommand):
    """
    土壌硬度測定データから3D表面プロットを生成するDjangoマネジメントコマンド

    このコマンドは2つの動作モードがあります:

    1. **特定圃場モード**:
       --land_ledger_id を指定すると、その1つの圃場のみの3D表面プロットを生成

    2. **全圃場一括モード**:
       --land_ledger_id を指定しないと、land_ledger_idが割り当てられている
       すべての圃場の3D表面プロットを一括生成

    出力ファイル形式:
    ---------------
    soil_hardness_{会社名}_{圃場名}_{日付}_3d_surface.png

    前提条件:
    --------
    - SoilHardnessMeasurement データが存在すること
    - 対象データに land_ledger_id が適切に割り当てられていること
    - 各圃場に複数の land_block と depth の測定データがあること
    """

    help = "土壌硬度測定データから3D表面プロットを生成"

    def add_arguments(self, parser):
        parser.add_argument("--output_dir", type=str, help="出力ディレクトリ")
        parser.add_argument("--land_ledger_id", type=int, help="特定の圃場台帳ID")

    def handle(self, *args, **options):
        """
        コマンド実行のメインロジック

        処理フロー:
        1. 出力ディレクトリの準備
        2. データ存在チェック
        3. 処理対象の決定（特定圃場 or 全圃場）
        4. 各圃場の3D表面プロット生成
        """
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

        # 処理対象データ取得
        target_data_queryset = SoilHardnessMeasurement.objects.filter(
            land_ledger__isnull=False
        )
        if options["land_ledger_id"]:
            target_data_queryset = target_data_queryset.filter(
                land_ledger_id=options["land_ledger_id"]
            )

        # 対象のland_ledger_idを取得
        land_ledger_ids = list(
            target_data_queryset.values_list("land_ledger_id", flat=True).distinct()
        )

        self.stdout.write(f"画像化する圃場数: {len(land_ledger_ids)}")

        if len(land_ledger_ids) == 0:
            self.stdout.write(
                self.style.WARNING("処理中断: 処理対象の圃場が見つかりません")
            )
            return

        # データ数の内訳を計算して表示
        data_per_field = assigned // len(land_ledger_ids)  # 1圃場あたりのデータ数
        blocks_per_field = 5  # 5ブロック想定
        measurements_per_block = 5  # 各ブロック5回計測想定
        total_measurements_per_field = blocks_per_field * measurements_per_block
        depth_data_count = (
            data_per_field // total_measurements_per_field
            if total_measurements_per_field > 0
            else 0
        )

        self.stdout.write(
            f"データ内訳: {assigned:,} ÷ {len(land_ledger_ids)} = {data_per_field:,}(1圃場あたり) "
            f"÷ {total_measurements_per_field}({blocks_per_field}ブロック×各{measurements_per_block}回計測) = "
            f"{depth_data_count}(深度データ数)"
        )

        # プロット作成
        plotter = SoilHardnessPlotterService(output_dir=output_dir)
        for land_ledger_id in land_ledger_ids:
            result_path = plotter.plot_3d_surface(land_ledger_id=land_ledger_id)
            if result_path:
                self.stdout.write(f"生成完了: {result_path}")
                self.stdout.write(f"Landモデルのimageフィールドに画像を保存しました")

        self.stdout.write(self.style.SUCCESS("完了"))
