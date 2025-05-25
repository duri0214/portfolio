from django.db.models import Count

from soil_analysis.models import SoilHardnessMeasurement, SamplingOrder, LandLedger


class SoilHardnessMeasurementRepository:
    @staticmethod
    def get_measurements_by_memory_range(memory_anchor: int, total_sampling_times: int):
        """
        指定されたメモリアンカーからtotal_sampling_times分の計測データを取得します

        Args:
            memory_anchor: 開始メモリ位置
            total_sampling_times: 計測データの総数

        Returns:
            QuerySet: SoilHardnessMeasurementのクエリセット
        """
        start_index = memory_anchor
        end_index = memory_anchor + (total_sampling_times - 1)

        return SoilHardnessMeasurement.objects.filter(
            set_memory__range=(start_index, end_index)
        ).order_by("pk")

    @staticmethod
    def group_measurements(queryset=None):
        """
        計測データをメモリセットごとにグループ化して取得します

        Args:
            queryset: 基となるクエリセット（指定がない場合は土地ブロックが割り当てられていない全てのSoilHardnessMeasurementを使用）

        Returns:
            QuerySet: メモリセットごとにグループ化された計測データ
        """
        if queryset is None:
            queryset = SoilHardnessMeasurement.objects.filter(land_block__isnull=True)

        return (
            queryset.values("set_memory", "set_datetime")
            .annotate(cnt=Count("pk"))
            .order_by("set_memory")
        )

    @staticmethod
    def calculate_total_sampling_times(land_ledger: LandLedger) -> int:
        """
        土壌硬度計測データの総採土回数を計算する

        Args:
            land_ledger: 対象の LandLedger インスタンス

        Returns:
            int: 総採土回数（ブロック数 × 1ブロックあたりの採土回数）
        """
        blocks = SamplingOrder.objects.filter(
            sampling_method=land_ledger.sampling_method
        ).count()
        sampling_times_per_block = 5  # 固定値として定義

        return blocks * sampling_times_per_block
