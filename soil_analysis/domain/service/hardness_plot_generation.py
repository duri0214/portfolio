import os

from django.core.files.base import ContentFile

from config import settings
from soil_analysis.domain.service.management.commands.soil_hardness_plotter import (
    SoilHardnessPlotterService,
)
from soil_analysis.domain.valueobject.management.commands.soil_hardness_plot import (
    SoilHardnessPlotName,
)
from soil_analysis.models import SoilHardnessMeasurement, LandLedger


def _generate_single_plot(land_ledger_id: int) -> bool:
    """
    単一のプロットを生成してLandLedgerモデルに保存

    Args:
        land_ledger_id: LandLedgerのID

    Returns:
        bool: 生成成功フラグ
    """
    land_ledger = LandLedger.objects.get(id=land_ledger_id)

    plotter = SoilHardnessPlotterService(output_dir=settings.MEDIA_ROOT)
    plot_path = plotter.plot_3d_surface(land_ledger_id)

    if plot_path:
        try:
            with open(plot_path, "rb") as f:
                filename = SoilHardnessPlotName.build_filename(
                    land_ledger_id=land_ledger_id,
                    sampling_date=land_ledger.sampling_date,
                )
                land_ledger.hardness_image.save(
                    filename, ContentFile(f.read()), save=True
                )
            os.remove(plot_path)
            return True
        except (OSError, PermissionError) as e:
            # ファイル削除エラーは無視して続行
            # OneDriveなどの同期フォルダではこの例外が発生することがある
            print(f"File operation error (ignoring): {e}")
            return True

    return False


class HardnessPlotGenerationService:
    @staticmethod
    def generate_and_save_plots(
        land_ledger_ids: list[int] | None = None,
    ) -> tuple[int, list[str]]:
        """
        関連付けされたデータからプロットを生成してLandLedgerモデルに保存

        Args:
            land_ledger_ids: 対象とするLandLedgerのIDリスト。Noneの場合は全ての関連付け済みデータを対象とする。

        Returns:
            tuple[int, list[str]]: (生成成功数, エラーメッセージリスト)
        """
        if land_ledger_ids is None:
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
