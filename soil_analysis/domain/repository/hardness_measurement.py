from django.db.models import Count, QuerySet

from soil_analysis.models import SoilHardnessMeasurement


class SoilHardnessMeasurementRepository:
    @staticmethod
    def get_measurements_by_memory_range(
        memory_anchor: int, total_sampling_times: int
    ) -> QuerySet:
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
    def group_measurements(queryset: QuerySet = None) -> QuerySet:
        """
        計測データをメモリセットごとにグループ化して取得します

        Args:
            queryset: 基となるクエリセット（指定がない場合は土地ブロックが割り当てられていない全てのSoilHardnessMeasurementを使用）

        Returns:
            QuerySet: メモリセットごとにグループ化された計測データ
            folder(圃場)別、set_memory(メモリ番号)別にソート
        """
        if queryset is None:
            queryset = SoilHardnessMeasurement.objects.filter(land_block__isnull=True)

        return (
            queryset.values("folder", "set_memory", "set_datetime")
            .annotate(cnt=Count("pk"))
            .order_by("folder", "set_memory")
        )
