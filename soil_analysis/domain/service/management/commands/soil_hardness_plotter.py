import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soil_analysis.models import SoilHardnessMeasurement


class SoilHardnessPlotterService:
    """土壌硬度測定データの3Dプロット生成サービス

    プロットは圃場内位置（X軸）、深度（Y軸）、圧力（Z軸）の3次元でPNG画像として保存されます。

    Attributes:
        output_dir (str): プロット画像の保存先ディレクトリパス
    """

    def __init__(self, output_dir: str = "."):
        self.output_dir = output_dir

    def plot_3d_surface(self, land_ledger_id: int | None = None) -> str:
        """土壌硬度測定データの3D表面プロットを生成

        指定されたland_ledger_idの土壌硬度測定データから3D表面プロットを生成し、
        PNG画像として保存します。land_ledger_idが未指定の場合は、全ての関連付け済み
        データを対象とします。

        Args:
            land_ledger_id (int | None, optional): 対象とする圃場帳簿のID。
                                                   Noneの場合は全関連付け済みデータが対象。
                                                   デフォルトはNone。

        Returns:
            str: 生成されたプロット画像のファイルパス。

        Raises:
            SoilHardnessMeasurement.DoesNotExist: 対象のデータが存在しない場合
            ValueError: データの処理中にインデックスエラーが発生した場合（継続処理）

        Note:
            - プロットのZ軸（圧力）は0-3000kPaに固定されます
            - 画像は300dpiの高解像度で保存されます
            - matplotlibのfigureは自動的にcloseされ、メモリリークを防ぎます
        """
        # データ取得
        queryset = SoilHardnessMeasurement.objects.select_related(
            "land_ledger__land", "land_block"
        ).order_by("depth")

        if land_ledger_id:
            queryset = queryset.filter(land_ledger_id=land_ledger_id)
        else:
            queryset = queryset.filter(land_ledger__isnull=False)

        first_data = queryset.first()
        if not first_data:
            target_info = (
                f"land_ledger_id={land_ledger_id}"
                if land_ledger_id
                else "all linked data"
            )
            raise SoilHardnessMeasurement.DoesNotExist(
                f"Soil hardness measurement data not found: {target_info}"
            )

        # 基本情報取得
        company_id = first_data.land_ledger.land.company_id
        land = first_data.land_ledger.land.name
        date = first_data.land_ledger.sampling_date.strftime("%Y%m%d")

        # データ整理
        land_block_names = list(
            queryset.values_list("land_block__name", flat=True)
            .distinct()
            .order_by("land_block__name")
        )
        depth_labels = sorted(queryset.values_list("depth", flat=True).distinct())

        pressure_data = np.full((len(land_block_names), len(depth_labels)), np.nan)

        for data in queryset:
            try:
                block_idx = land_block_names.index(data.land_block.name)
                depth_idx = depth_labels.index(data.depth)
                pressure_data[block_idx, depth_idx] = data.pressure
            except ValueError:
                continue

        # プロット作成
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        block_indices = np.arange(
            len(land_block_names)
        )  # 例: [0, 1, 2, 3] for ['A1', 'A3', 'B2', 'C1']
        depth_values = np.array(depth_labels)  # 例: [1, 5, 10, ..., 60]
        # 3Dプロット用のメッシュグリッド（格子）を作成
        block_grid, depth_grid = np.meshgrid(block_indices, depth_values)
        pressure_grid = pressure_data.T

        surf = ax.plot_surface(
            block_grid, depth_grid, pressure_grid, cmap="viridis", alpha=0.8
        )

        # X軸: ブロック名をスケール化（['A1', 'A3', 'B2'] → [0, 1, 2]）して等間隔表示
        ax.set_xticks(np.arange(len(land_block_names)))
        ax.set_xticklabels(land_block_names)
        ax.set_xlabel("block")  # X軸全体のラベル
        ax.set_ylabel("depth (cm)")  # Y軸: 深度（実際の深度値をそのまま使用）
        ax.set_zlabel("pressure (kPa)")  # Z軸: 圧力値（0-3000kPaの範囲で固定表示）
        ax.set_zlim(0, 3000)  # z軸を0-3000kPaに固定
        ax.set_title(f"company_{company_id} - {land} soil_hardness ({date})")

        # カラーバー追加（圧力値の色対応表を右側に表示）
        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label="kPa")

        # 保存
        filename = (
            f"soil_hardness_land_ledger_id_{land_ledger_id}_{date}_3d_surface.png"
        )
        save_path = os.path.join(self.output_dir, filename)
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

        return save_path
