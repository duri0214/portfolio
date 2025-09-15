from django.db.models import Count, QuerySet, Min, Max

from soil_analysis.models import SoilHardnessMeasurement, Land, LandLedger


class SoilHardnessMeasurementRepository:
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

        return list(folder_stats)

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
        return (
            SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
            .values("folder")
            .distinct()
            .count()
        )

    @staticmethod
    def get_folder_groups_for_association():
        """関連付け用のフォルダグループを取得

        各フォルダの代表データと統計情報を含む構造化されたデータを返します。
        HardnessAssociationViewで使用するためのメソッドです。

        Returns:
            list: フォルダグループ情報のリスト。例：
                [
                    {
                        "memory_anchor": 1,
                        "measurements": [<SoilHardnessMeasurement: 1>],
                        "folder_name": "静岡ススムA1_20230701",
                        "count": 150,
                        "min_memory": 1,
                        "max_memory": 5
                    },
                    {
                        "memory_anchor": 6,
                        "measurements": [<SoilHardnessMeasurement: 6>],
                        "folder_name": "静岡ススムA2_20230701",
                        "count": 120,
                        "min_memory": 6,
                        "max_memory": 9
                    }
                ]
        """
        # フォルダ単位でグループ化されたデータを取得
        folder_groups = (
            SoilHardnessMeasurement.objects.filter(land_block__isnull=True)
            .values("folder")
            .distinct()
        )

        # テンプレート用に構造を変換
        result = []
        for folder_group in folder_groups:
            folder_name = folder_group["folder"]

            # 該当フォルダのレコード数を取得
            total_count = SoilHardnessMeasurement.objects.filter(
                folder=folder_name, land_block__isnull=True
            ).count()

            # 代表データとして最初の1レコードのみを取得
            representative_measurement = (
                SoilHardnessMeasurement.objects.filter(
                    folder=folder_name, land_block__isnull=True
                )
                .order_by("set_memory", "depth")
                .first()
            )

            if representative_measurement:
                # メモリー番号の範囲を計算
                memory_numbers = list(
                    SoilHardnessMeasurement.objects.filter(
                        folder=folder_name, land_block__isnull=True
                    )
                    .values_list("set_memory", flat=True)
                    .distinct()
                )
                min_memory = (
                    min(memory_numbers)
                    if memory_numbers
                    else representative_measurement.set_memory
                )
                max_memory = (
                    max(memory_numbers)
                    if memory_numbers
                    else representative_measurement.set_memory
                )

                group = {
                    "memory_anchor": representative_measurement.set_memory,
                    "measurements": [representative_measurement],  # 代表データ1件のみ
                    "folder_name": folder_name,
                    "count": total_count,
                    "min_memory": min_memory,
                    "max_memory": max_memory,
                }
                result.append(group)

        return result
