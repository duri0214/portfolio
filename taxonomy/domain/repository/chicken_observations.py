from django.db.models import Sum

from taxonomy.models import EggLedger


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

    @staticmethod
    def get_feed_vs_egg_production():
        """
        日付ごとの餌投入量（FeedGroup）と卵生産量（EggLedger）の関係を関連付けたデータを取得し、
        None値をゼロ埋めします。
        :return: [{'recorded_date': '2023-10-01', 'total_feed': 50, 'total_eggs': 30}, ...]
        """
        queryset = (
            EggLedger.objects.values(
                "recorded_date", "egg_count"
            )  # 卵生産数をそのまま使用
            .annotate(
                # EggLedgerと関連付けられたFeedGroupのweightを合計
                total_feed=Sum("feed_group__weight")  # 餌投入量だけ集計
            )
            .order_by("recorded_date")
        )

        # QuerySetを辞書形式に変換し、Noneの値をゼロで埋める
        raw_data = ChickenObservationsRepository.to_dict(
            queryset, date_fields=["recorded_date"]
        )

        # NaN発生防止のためゼロ埋め処理を追加
        processed_data = []
        for entry in raw_data:
            processed_data.append(
                {
                    "recorded_date": entry.get(
                        "recorded_date", ""
                    ),  # 日付は空でなくそのまま使用
                    "total_feed": entry.get("total_feed", 0)
                    or 0,  # NoneまたはFalseなら0
                    "total_eggs": entry.get("egg_count", 0)
                    or 0,  # NoneまたはFalseなら0
                }
            )

        return processed_data
