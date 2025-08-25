from welfare_services.models import Facility, FacilityAvailability


class FacilityRepository:
    """施設データのリポジトリクラス

    ビジネスロジックとデータアクセスの関心を分離するためのリポジトリパターンの実装。
    施設に関するクエリロジックをここに集約することで、ビューの肥大化を防ぎます。
    """

    @staticmethod
    def get_all_facilities():
        """すべての施設を取得する"""
        return Facility.objects.all().order_by("name")

    @staticmethod
    def get_facilities_count():
        """施設の総数を取得する"""
        return Facility.objects.count()

    @staticmethod
    def get_last_updated_facility():
        """最後に更新された施設を取得する"""
        return Facility.objects.order_by("-updated_at").first()

    @staticmethod
    def get_recent_facilities(limit=6):
        """最近更新された施設を取得する

        Args:
            limit: 取得する施設の数

        Returns:
            最近更新された施設のリスト
        """
        return Facility.objects.all().order_by("-updated_at")[:limit]

    @staticmethod
    def get_facility_by_id(facility_id):
        """IDで施設を取得する"""
        return Facility.objects.filter(id=facility_id).first()

    @staticmethod
    def get_latest_availability(facility):
        """指定された施設の最新の空き状況を取得する"""
        return (
            FacilityAvailability.objects.filter(facility=facility)
            .order_by("-target_date")
            .first()
        )

    @staticmethod
    def get_facility_availabilities(facility):
        """指定された施設のすべての空き状況を取得する"""
        return FacilityAvailability.objects.filter(facility=facility).order_by(
            "-target_date"
        )

    @staticmethod
    def get_facilities_with_filter(name=None, area=None):
        """名前とエリアでフィルタリングされた施設を取得する"""
        facilities = FacilityRepository.get_all_facilities()

        if name:
            facilities = facilities.filter(name__icontains=name)
        if area:
            facilities = facilities.filter(address__icontains=area)

        return facilities

    @staticmethod
    def get_sorted_facilities_by_availability(facilities, status=None):
        """空き状況に基づいて施設をソートする

        空き状況によって以下の順でソート：
        1. 空きあり
        2. 残りわずか
        3. 空きなし
        4. 未登録

        Args:
            facilities: ソートする施設のクエリセット
            status: フィルタリングする空き状況（指定された場合）

        Returns:
            ソートされた施設のリスト
        """
        return FacilityRepository._classify_facilities_by_availability(
            facilities, status
        )

    @staticmethod
    def _classify_facilities_by_availability(facilities, status=None):
        """空き状況に基づいて施設を分類する内部メソッド

        Args:
            facilities: 分類する施設のクエリセットまたはリスト
            status: フィルタリングする空き状況（指定された場合）

        Returns:
            空き状況によって分類・ソートされた施設のリスト
        """
        facilities_by_status = {
            "available": [],  # 空きあり
            "limited": [],  # 残りわずか
            "unavailable": [],  # 空きなし
            "none": [],  # 未登録
        }

        for facility in facilities:
            # 最新の空き状況を取得し、施設オブジェクトに追加
            latest_availability = FacilityRepository.get_latest_availability(facility)
            facility.latest_availability = latest_availability

            # 空き状況による分類
            if not latest_availability:
                # 空き状況が未登録の場合
                if not status:  # フィルターがない場合のみ追加
                    facilities_by_status["none"].append(facility)
            elif status and latest_availability.status != status:
                # ステータスフィルターが指定され、それに一致しない場合はスキップ
                continue
            else:
                # 空き状況によって分類
                facilities_by_status[latest_availability.status].append(facility)

        # 空き状況順に結合（空きあり → 残りわずか → 空きなし → 未登録）
        result = (
            facilities_by_status["available"]
            + facilities_by_status["limited"]
            + facilities_by_status["unavailable"]
        )

        # 未登録施設は、フィルターがない場合のみ追加
        if not status:
            result += facilities_by_status["none"]

        return result
