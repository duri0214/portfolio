from django.contrib.auth import get_user_model
from django.db.models import Count, Min, Max

from soil_analysis.models import (
    Land,
    Crop,
    LandPeriod,
    SamplingMethod,
    Company,
    SoilHardnessMeasurement,
    SoilHardnessMeasurementImportErrors,
)
from soil_analysis.domain.repository.hardness_measurement import (
    SoilHardnessMeasurementRepository,
)


class LandLedgerRepository:
    """
    LandLedger関連のデータアクセスを担当するRepository
    """

    @staticmethod
    def get_form_data_for_ajax(folder_name: str) -> dict:
        """
        フォーム表示用データをAjaxで取得
        フォルダ名から圃場を推定する処理も含む

        Args:
            folder_name: フォルダ名

        Returns:
            フォーム表示用のデータ辞書
        """
        # 圃場の選択肢を取得し、フォルダ名から推定
        lands = (
            Land.objects.all()
            .select_related("company")
            .order_by("company__name", "name")
        )
        suggested_land = None

        if folder_name:
            # フォルダ名から圃場を推定（部分一致）
            for land in lands:
                if (
                    land.name.lower() in folder_name.lower()
                    or folder_name.lower() in land.name.lower()
                ):
                    suggested_land = land
                    break

        # フォルダ名からSoilHardnessMeasurementの最新set_datetimeを取得
        suggested_sampling_date = None
        if folder_name:
            latest_measurement = (
                SoilHardnessMeasurement.objects.filter(folder=folder_name)
                .order_by("-set_datetime")
                .first()
            )

            if latest_measurement:
                suggested_sampling_date = latest_measurement.set_datetime.date()

        # 各選択肢のデータを構築
        response_data = {
            "lands": [
                {
                    "id": land.id,
                    "name": f"{land.company.name} - {land.name}",
                    "selected": (
                        land.id == suggested_land.id if suggested_land else False
                    ),
                }
                for land in lands
            ],
            "crops": [
                {"id": crop.id, "name": crop.name} for crop in Crop.objects.all()
            ],
            "land_periods": [
                {"id": period.id, "name": f"{period.year} {period.name}"}
                for period in LandPeriod.objects.all().order_by("-year", "name")
            ],
            "sampling_methods": [
                {
                    "id": method.id,
                    "name": method.name,
                    "selected": "5点法" in method.name,
                }
                for method in SamplingMethod.objects.all()
            ],
            "analytical_agencies": [
                {"id": company.id, "name": company.name}
                for company in Company.objects.filter(category_id=2)
            ],
            "sampling_staff": [
                {"id": user.id, "name": user.get_username()}
                for user in get_user_model().objects.all()
            ],
            "suggested_land_id": suggested_land.id if suggested_land else None,
            "suggested_sampling_date": (
                suggested_sampling_date.isoformat() if suggested_sampling_date else None
            ),
            "folder_name": folder_name,
        }

        return response_data

    @staticmethod
    def get_association_success_context() -> dict:
        """
        関連付け完了画面用のコンテキストデータを取得

        Returns:
            コンテキストデータ辞書
        """
        # 関連付けされたデータのみを対象とする（land_ledgerとland_blockが設定済み）
        associated_measurements = SoilHardnessMeasurement.objects.filter(
            land_ledger__isnull=False, land_block__isnull=False
        )

        # CSVインポートされた硬度測定データをフォルダ名でグループ化し、各フォルダの統計情報を取得
        folder_stats = SoilHardnessMeasurementRepository.get_folder_stats(
            associated_only=True
        )

        # 各フォルダで使用された機材名とland_block、land_ledger情報を取得
        folder_devices = {}
        folder_blocks = {}
        folder_ledgers = {}

        for measurement in (
            associated_measurements.select_related(
                "set_device", "land_block", "land_ledger__land", "land_ledger__crop"
            )
            .values(
                "folder",
                "set_device__name",
                "land_block__name",
                "land_ledger__land__name",
                "land_ledger__sampling_date",
                "land_ledger__crop__name",
            )
            .distinct()
            .order_by("folder", "land_block__name")  # フォルダとland_block名でソート
        ):
            folder = measurement["folder"]

            # デバイス情報
            device_name = measurement["set_device__name"]
            if folder not in folder_devices:
                folder_devices[folder] = []
            if device_name and device_name not in folder_devices[folder]:
                folder_devices[folder].append(device_name)

            # land_block情報
            block_name = measurement["land_block__name"]
            if folder not in folder_blocks:
                folder_blocks[folder] = []
            if block_name and block_name not in folder_blocks[folder]:
                folder_blocks[folder].append(block_name)

        # 各フォルダのland_block名をソート
        for folder in folder_blocks:
            folder_blocks[folder].sort()

        # land_ledger情報を収集
        for measurement in (
            associated_measurements.select_related(
                "set_device", "land_block", "land_ledger__land", "land_ledger__crop"
            )
            .values(
                "folder",
                "land_ledger__land__name",
                "land_ledger__sampling_date",
                "land_ledger__crop__name",
            )
            .distinct()
        ):
            folder = measurement["folder"]
            if folder not in folder_ledgers:
                folder_ledgers[folder] = []
            ledger_info = {
                "land_name": measurement["land_ledger__land__name"],
                "sampling_date": measurement["land_ledger__sampling_date"],
                "crop_name": measurement["land_ledger__crop__name"],
            }
            if ledger_info not in folder_ledgers[folder]:
                folder_ledgers[folder].append(ledger_info)

        # folder_statsに関連付け情報を追加
        folder_stats_with_details = []
        for stats in folder_stats:
            stats["device_names"] = folder_devices.get(stats["folder"], [])
            stats["land_block_names"] = folder_blocks.get(stats["folder"], [])
            stats["land_ledger_info"] = folder_ledgers.get(stats["folder"], [])
            folder_stats_with_details.append(stats)

        # Land Block別集計
        land_block_stats = (
            associated_measurements.select_related("land_block")
            .values("land_block__name")
            .annotate(
                count=Count("id"),
                set_depth=Min("set_depth"),  # 設定深度を表示（通常は固定値60cm）
                min_pressure=Min("pressure"),
                max_pressure=Max("pressure"),
            )
            .order_by("land_block__name")
        )

        # Land Ledger別集計
        land_ledger_stats = (
            associated_measurements.select_related(
                "land_ledger__land", "land_ledger__crop", "land_ledger__land_period"
            )
            .values(
                "land_ledger__land__name",
                "land_ledger__sampling_date",
                "land_ledger__crop__name",
                "land_ledger__land_period__name",
            )
            .annotate(
                count=Count("id"),
            )
            .order_by("land_ledger__sampling_date")
        )

        # レスポンス用にフィールド名を整理
        land_block_stats_formatted = [
            {
                "land_block_name": stat["land_block__name"],
                "count": stat["count"],
                "set_depth": stat["set_depth"],
                "min_pressure": stat["min_pressure"],
                "max_pressure": stat["max_pressure"],
            }
            for stat in land_block_stats
        ]

        land_ledger_stats_formatted = [
            {
                "land_name": stat["land_ledger__land__name"],
                "sampling_date": stat["land_ledger__sampling_date"],
                "crop_name": stat["land_ledger__crop__name"],
                "period_name": stat["land_ledger__land_period__name"],
                "count": stat["count"],
            }
            for stat in land_ledger_stats
        ]

        return {
            "import_errors": SoilHardnessMeasurementImportErrors.objects.all(),
            "folder_stats": folder_stats_with_details,
            "land_block_stats": land_block_stats_formatted,
            "land_ledger_stats": land_ledger_stats_formatted,
            "total_records": associated_measurements.count(),
        }
