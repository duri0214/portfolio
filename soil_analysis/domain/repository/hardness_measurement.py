from django.db.models import Count, QuerySet, Min, Max

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

    @staticmethod
    def get_folder_stats(associated_only: bool = False) -> QuerySet:
        """
        フォルダ別の統計情報を取得します

        Args:
            associated_only: Trueの場合は関連付け済み（land_ledger, land_blockが設定済み）のデータのみを対象とする
                            Falseの場合は全てのデータを対象とする

        Returns:
            QuerySet: フォルダ別統計情報（レコード数、メモリ番号範囲、測定日時範囲）
        """
        if associated_only:
            # 関連付け済みデータのみを対象（HardnessAssociationSuccessView用）
            queryset = SoilHardnessMeasurement.objects.filter(
                land_ledger__isnull=False, land_block__isnull=False
            ).select_related(
                "set_device",
                "land_block",
                "land_ledger__land",
                "land_ledger__crop",
                "land_ledger__land_period",
            )
            return (
                queryset.values("folder")
                .annotate(
                    count=Count("id", distinct=True),
                    min_datetime=Min("set_datetime"),
                    max_datetime=Max("set_datetime"),
                )
                .order_by("folder")
            )
        else:
            # 全データを対象（HardnessSuccessView用）
            return (
                SoilHardnessMeasurement.objects.select_related("set_device")
                .values("folder")
                .annotate(
                    count=Count("id"),
                    min_memory=Min("set_memory"),
                    max_memory=Max("set_memory"),
                    min_datetime=Min("set_datetime"),
                    max_datetime=Max("set_datetime"),
                )
                .order_by("folder")
            )
