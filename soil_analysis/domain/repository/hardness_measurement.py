from django.db.models import Count, Min, Max, Avg

from soil_analysis.domain.valueobject.hardness import FolderStats
from soil_analysis.models import SoilHardnessMeasurement, LandLedger, Land


class SoilHardnessMeasurementRepository:
    """
    土壌硬度測定データのデータアクセスを担当するRepository
    """

    @staticmethod
    def get_folder_stats(associated_only: bool = False) -> list[FolderStats]:
        """
        フォルダ別の統計情報を取得します

        Args:
            associated_only: データの処理段階に応じて対象を絞り込む
                           False: CSVインポート直後の全データが対象
                           True:  圃場関連付け完了後のデータが対象

        Returns:
            list[FolderStats]: フォルダ別統計情報のリスト

        Examples:
            [
                FolderStats(
                    folder='20230601_FieldA',
                    device_name='DIK-5531',
                    count=50,
                    min_memory=1,
                    max_memory=50,
                    min_datetime=datetime(2023, 6, 1, 10, 0),
                    max_datetime=datetime(2023, 6, 1, 11, 0)),
            ]
        """
        # 基本クエリを構築
        queryset = SoilHardnessMeasurement.objects.select_related("set_device")

        # 条件に応じて絞り込み
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

        return [
            FolderStats(
                folder=stat["folder"],
                device_name=stat["set_device__name"],
                count=stat["count"],
                min_memory=stat["min_memory"],
                max_memory=stat["max_memory"],
                min_datetime=stat["min_datetime"],
                max_datetime=stat["max_datetime"],
            )
            for stat in folder_stats
        ]

    @staticmethod
    def create(measurement: SoilHardnessMeasurement) -> SoilHardnessMeasurement:
        """
        測定データを1件登録します。

        Args:
            measurement: 保存するインスタンス

        Returns:
            SoilHardnessMeasurement: 保存されたインスタンス
        """
        # ルール34に従い、1件の更新・保存であってもリスト + bulk_update を推奨しているが、
        # 新規作成(create)に関しては言及がないため、通常のsaveを使用
        measurement.save()
        return measurement

    @staticmethod
    def bulk_update(
        measurements: list[SoilHardnessMeasurement], fields: list[str]
    ) -> None:
        """
        測定データを一括更新します（ルール32, 34準拠）。

        Args:
            measurements: 更新対象のインスタンスリスト
            fields: 更新するフィールド名のリスト
        """
        SoilHardnessMeasurement.objects.bulk_update(measurements, fields=fields)

    @staticmethod
    def get_first_by_memory_anchor(
        memory_anchor: int,
    ) -> SoilHardnessMeasurement | None:
        """
        指定されたメモリーアンカー（代表メモリー番号）を持つ最初のデータを取得します。

        Args:
            memory_anchor: メモリー番号

        Returns:
            SoilHardnessMeasurement | None: 該当するデータ、存在しない場合はNone
        """
        return SoilHardnessMeasurement.objects.filter(set_memory=memory_anchor).first()

    @staticmethod
    def get_all_by_folder(folder_name: str) -> list[SoilHardnessMeasurement]:
        """
        指定されたフォルダ名に属する全てのデータを取得します。

        Args:
            folder_name: フォルダ名

        Returns:
            list[SoilHardnessMeasurement]: 測定データのリスト
        """
        return list(
            SoilHardnessMeasurement.objects.filter(folder=folder_name).order_by(
                "set_memory", "depth"
            )
        )

    @staticmethod
    def get_suitable_ledgers(folder_name: str) -> list[LandLedger]:
        """
        フォルダ名に基づいて適切な帳簿を取得します（使用済み帳簿は除外）。

        Args:
            folder_name: フォルダ名

        Returns:
            list[LandLedger]: 適合する帳簿のリスト
        """
        # 既に硬度データに関連付けられた帳簿のIDを取得
        used_ledger_ids = (
            SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
            .values_list("land_ledger_id", flat=True)
            .distinct()
        )

        # 基本クエリ：使用済み帳簿を除外
        base_query = LandLedger.objects.exclude(id__in=used_ledger_ids)

        # フォルダ名による絞り込み
        if folder_name:
            # フォルダ名に含まれるキーワードで圃場を検索
            lands = Land.objects.filter(name__icontains=folder_name.split("_")[0])
            if lands.exists():
                company = lands.first().company
                return list(base_query.filter(land__company=company).distinct())

        # 該当なしの場合は未使用の全帳簿を返す
        return list(base_query.order_by("pk"))

    @staticmethod
    def get_block_averages(land_ledger: LandLedger) -> dict[str, float | None]:
        """
        指定された台帳に紐づくブロックごとの平均圧力を取得します。

        Args:
            land_ledger: 台帳インスタンス

        Returns:
            dict[str, float | None]: ブロック名をキー、平均圧力を値とする辞書
        """
        stats = (
            SoilHardnessMeasurement.objects.filter(land_ledger=land_ledger)
            .values("land_block__name")
            .annotate(avg_pressure=Avg("pressure"))
        )
        return {
            item["land_block__name"]: item["avg_pressure"]
            for item in stats
            if item["land_block__name"]
        }

    @staticmethod
    def get_depth_averages(land_ledger: LandLedger) -> list[dict]:
        """
        指定された台帳に紐づくブロックごと、深度ごとの平均圧力を取得します。

        Args:
            land_ledger: 台帳インスタンス

        Returns:
            list[dict]: ブロック名、深度、平均圧力を含む辞書のリスト
        """
        return list(
            SoilHardnessMeasurement.objects.filter(land_ledger=land_ledger)
            .values("land_block__name", "depth")
            .annotate(avg_pressure=Avg("pressure"))
            .order_by("land_block__name", "depth")
        )

    @staticmethod
    def get_total_groups_count() -> int:
        """
        総フォルダグループ数を取得します。

        Returns:
            int: 総グループ数
        """
        return SoilHardnessMeasurement.objects.values("folder").distinct().count()

    @staticmethod
    def get_processed_groups_count() -> int:
        """
        処理済みフォルダグループ数を取得します。

        Returns:
            int: 処理済みグループ数
        """
        return (
            SoilHardnessMeasurement.objects.filter(land_ledger__isnull=False)
            .values("folder")
            .distinct()
            .count()
        )

    @staticmethod
    def get_folder_groups_for_association() -> list[dict]:
        """
        関連付け用のフォルダグループを取得します。

        Returns:
            list[dict]: フォルダグループ情報のリスト
        """
        # フォルダ単位でグループ化されたデータを取得
        folder_groups = (
            SoilHardnessMeasurement.objects.filter(land_block__isnull=True)
            .values("folder")
            .distinct()
        )

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
                min_memory = min(memory_numbers)
                max_memory = max(memory_numbers)

                group = {
                    "memory_anchor": representative_measurement.set_memory,
                    "measurements": [representative_measurement],
                    "folder_name": folder_name,
                    "count": total_count,
                    "min_memory": min_memory,
                    "max_memory": max_memory,
                }
                result.append(group)

        return result
