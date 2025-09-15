from django.db.models import Count, QuerySet, Min, Max

from soil_analysis.models import SoilHardnessMeasurement, Land, LandLedger


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
    def get_folder_stats(associated_only: bool = False) -> list:
        """
        フォルダ別の統計情報を取得します

        戻り値例：
        [
            {
                "folder": "folder_A",
                "device_name": "DIK-5531",
                "count": 100,
                "min_memory": 1,
                "max_memory": 5,
                "min_datetime": datetime(2023, 7, 1, 9, 0),
                "max_datetime": datetime(2023, 7, 1, 17, 0)
            },
            {
                "folder": "folder_B",
                "device_name": "DIK-5532",
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
        folder_stats = (
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

        # テンプレート用にフィールド名を調整
        result = []
        for stats in folder_stats:
            stats_dict = dict(stats)
            # set_device__nameをdevice_nameにリネーム
            stats_dict["device_name"] = (
                stats_dict.pop("set_device__name", None) or "不明"
            )
            result.append(stats_dict)

        return result

    @staticmethod
    def get_suitable_ledgers(folder_name: str):
        """フォルダ名に基づいて適切な帳簿を取得"""
        if folder_name:
            # フォルダ名に含まれるキーワードで圃場を検索
            lands = Land.objects.filter(name__icontains=folder_name.split("_")[0])
            if lands.exists():
                company = lands.first().company
                return LandLedger.objects.filter(land__company=company).distinct()

        # 該当なしの場合は全帳簿を返す
        return LandLedger.objects.all().order_by("pk")

    @staticmethod
    def get_total_groups_count():
        """総フォルダグループ数を取得"""
        return SoilHardnessMeasurement.objects.values("folder").distinct().count()

    @staticmethod
    def get_processed_groups_count():
        """処理済みフォルダグループ数を取得"""
        # 各フォルダで少なくとも1レコードがland_ledgerに関連付けられているフォルダ数をカウント
        return (
            SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
            .values("folder")
            .distinct()
            .count()
        )
