from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
)
from soil_analysis.domain.valueobject.report.hardness_assessment import (
    HardnessAssessmentVO,
)
from soil_analysis.models import LandLedger


class HardnessMeasurementService:
    """
    土壌硬度測定データの集計サービス。
    """

    @staticmethod
    def get_hardness_assessment(land_ledger: LandLedger) -> HardnessAssessmentVO:
        """
        指定された台帳に紐づく硬度データをブロックごとに集計し、HardnessAssessmentVOを返す。

        Args:
            land_ledger: 集計対象の台帳

        Returns:
            HardnessAssessmentVO: 集計結果
        """
        # 1. ブロックごとの平均圧力を計算
        measurements_by_block = SoilHardnessMeasurementRepository.get_block_averages(
            land_ledger
        )

        # 2. ブロックごと、深度ごとの平均圧力を計算（スパークライン用）
        depth_stats = SoilHardnessMeasurementRepository.get_depth_averages(land_ledger)

        depth_data_by_block = {}
        for item in depth_stats:
            block_name = item["land_block__name"]
            if not block_name:
                continue
            if block_name not in depth_data_by_block:
                depth_data_by_block[block_name] = []
            depth_data_by_block[block_name].append(
                (item["depth"], item["avg_pressure"])
            )

        # 9ブロックすべてを網羅するように補完
        all_block_names = [
            f"{col}{row}" for row in ["1", "2", "3"] for col in ["A", "B", "C"]
        ]
        for name in all_block_names:
            if name not in measurements_by_block:
                measurements_by_block[name] = None
            if name not in depth_data_by_block:
                depth_data_by_block[name] = []

        return HardnessAssessmentVO.from_measurements(
            measurements_by_block, depth_data_by_block
        )
