from django.db.models import Count, Sum

from taxonomy.models import EggLedger, FeedWeight


class ChickenObservationsRepository:
    """
    FeedWeight, EggLedger, HenGroupを管理する
    鶏観察用のリポジトリクラス
    """

    # ------ データ変換用ヘルパー ------
    @staticmethod
    def to_dict(queryset, date_fields=None):
        """
        QuerySetを辞書リストに変換
        必要に応じて日付フィールドをISO形式に変換
        :param queryset: QuerySetまたはリスト
        :param date_fields: ISO形式に変換するフィールド名のリスト
        :return: 辞書リスト
        """
        date_fields = date_fields or []  # デフォルトは空リスト

        result = []
        for record in queryset:
            record_dict = dict(record)
            # 日付フィールドをISO形式に変換
            for date_field in date_fields:
                if date_field in record_dict and record_dict[date_field] is not None:
                    record_dict[date_field] = record_dict[date_field].isoformat()
            result.append(record_dict)
        return result

    # ------ 餌のデータ操作 ------
    @staticmethod
    def get_feed_usage_by_type():
        """
        餌の種類ごとの総投入量を取得（辞書形式）
        """
        queryset = (
            FeedWeight.objects.values("name")
            .annotate(total_weight=Sum("weight"))
            .order_by("-total_weight")
        )
        return ChickenObservationsRepository.to_dict(queryset)

    # ------ 卵生産データ操作 ------
    @staticmethod
    def get_egg_production_by_date():
        """
        日ごとの卵生産数を取得（辞書形式）
        """
        queryset = (
            EggLedger.objects.values("recorded_date")
            .annotate(total_eggs=Count("id"))
            .order_by("recorded_date")
        )
        return ChickenObservationsRepository.to_dict(
            queryset, date_fields=["recorded_date"]
        )
