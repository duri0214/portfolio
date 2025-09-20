from django.core.files.base import ContentFile
from soil_analysis.models import SoilHardnessMeasurement, LandLedger
from soil_analysis.domain.service.management.commands.soil_hardness_plotter import (
    SoilHardnessPlotterService,
)


def _generate_single_plot(land_ledger_id: int) -> bool:
    """
    単一のプロットを生成してLandモデルに保存

    Args:
        land_ledger_id: LandLedgerのID

    Returns:
        bool: 生成成功フラグ
    """
    land_ledger = LandLedger.objects.get(id=land_ledger_id)

    plotter = SoilHardnessPlotterService()
    plot_path = plotter.plot_3d_surface(land_ledger_id)

    if plot_path:
        with open(plot_path, "rb") as f:
            filename = f"land_{land_ledger.land.id}_{land_ledger.sampling_date.strftime('%Y%m%d')}_3d_surface.png"
            land_ledger.land.image.save(filename, ContentFile(f.read()), save=True)
        return True

    return False


class HardnessPlotGenerationService:
    @staticmethod
    def generate_and_save_plots() -> tuple[int, list[str]]:
        """
        関連付けされたデータからプロットを生成してLandモデルに保存

        Returns:
            tuple[int, list[str]]: (生成成功数, エラーメッセージリスト)
        """
        land_ledger_ids = list(
            SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
            .values_list("land_ledger_id", flat=True)
            .distinct()
        )

        if not land_ledger_ids:
            return 0, []

        generated_count = 0
        errors = []

        for land_ledger_id in land_ledger_ids:
            try:
                success = _generate_single_plot(land_ledger_id)
                if success:
                    generated_count += 1
            except Exception as e:
                errors.append(f"圃場ID {land_ledger_id}の画像生成でエラー: {str(e)}")

        return generated_count, errors
