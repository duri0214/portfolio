import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from soil_analysis.models import SoilHardnessMeasurement


class SoilHardnessPlotterService:
    def __init__(self, output_dir="."):
        self.output_dir = output_dir
        plt.rcParams["font.family"] = ["IPAexGothic"]

    def plot_3d_surface(self, land_ledger_id=None, folder=None):
        # データ取得
        queryset = SoilHardnessMeasurement.objects.select_related(
            "land_ledger__land__company", "land_ledger__land", "land_block"
        ).order_by("depth")

        if land_ledger_id:
            queryset = queryset.filter(land_ledger_id=land_ledger_id)
        else:
            queryset = queryset.filter(land_ledger__isnull=False)

        if folder:
            queryset = queryset.filter(folder=folder)

        first_data = queryset.first()
        if not first_data:
            return

        # 基本情報取得
        company = first_data.land_ledger.land.company.name
        land = first_data.land_ledger.land.name
        date = first_data.land_ledger.sampling_date.strftime("%Y%m%d")

        if folder:
            land = f"{land}_{folder}"

        # データ整理
        locations = list(
            queryset.values_list("land_block__name", flat=True)
            .distinct()
            .order_by("land_block__name")
        )
        depths = sorted(queryset.values_list("depth", flat=True).distinct())

        pressure_data = np.full((len(locations), len(depths)), np.nan)

        for data in queryset:
            try:
                loc_idx = locations.index(data.land_block.name)
                depth_idx = depths.index(data.depth)
                pressure_data[loc_idx, depth_idx] = data.pressure
            except ValueError:
                continue

        # プロット作成
        fig = plt.figure(figsize=(12, 8))
        ax = fig.add_subplot(111, projection="3d")

        x = np.arange(len(locations))
        y = np.array(depths)
        x, y = np.meshgrid(x, y)
        z = pressure_data.T

        surf = ax.plot_surface(x, y, z, cmap="viridis", alpha=0.8)

        ax.set_xticks(np.arange(len(locations)))
        ax.set_xticklabels(locations)
        ax.set_xlabel("圃場内位置")
        ax.set_ylabel("深度 (cm)")
        ax.set_zlabel("圧力 (kPa)")
        ax.set_title(f"{company} - {land} 土壌硬度分布 ({date})")

        fig.colorbar(surf, ax=ax, shrink=0.5, aspect=5, label="圧力 (kPa)")

        # 保存
        filename = f"soil_hardness_{company}_{land}_{date}_3d_surface.png"
        save_path = os.path.join(self.output_dir, filename)
        plt.savefig(save_path, dpi=300, bbox_inches="tight")
        plt.close(fig)
