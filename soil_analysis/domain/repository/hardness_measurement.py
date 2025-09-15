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

        戻り値例：
        [
            {
                "folder": "folder_A",
                "set_device__name": "DIK-5531",
                "count": 100,
                "min_memory": 1,
                "max_memory": 5,
                "min_datetime": datetime(2023, 7, 1, 9, 0),
                "max_datetime": datetime(2023, 7, 1, 17, 0)
            },
            {
                "folder": "folder_B",
                "set_device__name": "DIK-5532",
                "count": 50,
                "min_memory": 6,
                "max_memory": 8,
                "min_datetime": datetime(2023, 7, 2, 10, 0),
                "max_datetime": datetime(2023, 7, 2, 16, 0)
            }
        ]

        Args:
            associated_only: データの処理段階に応じて対象を絞り込む
                           False: CSVインポート直後の全データが対象（HardnessSuccessView用）
                                 - インポートされた全ての測定データを集計
                                 - まだ圃場との関連付けが行われていない状態
                           True:  圃場関連付け完了後のデータが対象（HardnessAssociationSuccessView用）
                                 - land_ledger, land_blockが設定済みのデータのみを集計
                                 - 関連付け処理が完了した測定データの最終結果表示用

        Returns:
            QuerySet: フォルダ別統計情報（レコード数、メモリ番号範囲、測定日時範囲、デバイス名）
        """
        # 基本クエリを構築
        queryset = SoilHardnessMeasurement.objects.select_related("set_device")

        # 条件に応じて絞り込みとselect_relatedを追加
        if associated_only:
            queryset = queryset.filter(
                land_ledger__isnull=False, land_block__isnull=False
            ).select_related(
                "land_block",
                "land_ledger__land",
                "land_ledger__crop",
                "land_ledger__land_period",
            )
            count_field = Count("id", distinct=True)
        else:
            count_field = Count("id")

        # 共通の集計処理
        return (
            queryset.values("folder", "set_device__name")
            .annotate(
                count=count_field,
                min_memory=Min("set_memory"),
                max_memory=Max("set_memory"),
                min_datetime=Min("set_datetime"),
                max_datetime=Max("set_datetime"),
            )
            .order_by("folder")
        )
