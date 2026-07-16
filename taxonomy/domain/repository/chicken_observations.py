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
        日付ごとの餌投入量・卵生産量・産卵率・天気を表示用に取得します。

        :return: [{'recorded_date': '2023-10-01', 'total_feed': 50, 'total_eggs': 30, ...}, ...]
        """
        queryset = EggLedger.objects.select_related(
            "feed_group",
            "hen_group",
            "weather_code",
        ).order_by("recorded_date")

        return [
            {
                "recorded_date": ledger.recorded_date.isoformat(),
                "total_feed": ledger.feed_group.weight if ledger.feed_group else 0,
                "feed_group": str(ledger.feed_group) if ledger.feed_group else "",
                "total_eggs": ledger.egg_count or 0,
                "laying_rate": ledger.laying_rate(),
                "weather_code": ledger.weather_code.summary_code,
                "weather_name": ledger.weather_code.name,
            }
            for ledger in queryset
        ]

    @staticmethod
    def get_observation_summary():
        """
        餌の量・天気ごとの比較前提と平均値を画面表示向けに集計します。
        """
        ledgers = list(
            EggLedger.objects.select_related(
                "feed_group",
                "hen_group",
                "weather_code",
            ).order_by("recorded_date")
        )
        if not ledgers:
            return {
                "record_count": 0,
                "start_date": "",
                "end_date": "",
                "feed_summaries": [],
                "weather_summaries": [],
            }

        feed_summaries = ChickenObservationsRepository._summarize_by_feed(ledgers)
        weather_summaries = ChickenObservationsRepository._summarize_by_weather(ledgers)

        return {
            "record_count": len(ledgers),
            "start_date": ledgers[0].recorded_date.isoformat(),
            "end_date": ledgers[-1].recorded_date.isoformat(),
            "feed_summaries": feed_summaries,
            "weather_summaries": weather_summaries,
        }

    @staticmethod
    def _summarize_by_feed(ledgers):
        data_by_weight = {}
        for ledger in ledgers:
            weight = ledger.feed_group.weight
            data_by_weight.setdefault(weight, []).append(ledger)

        summaries = []
        for weight, records in sorted(data_by_weight.items(), reverse=True):
            summaries.append(
                {
                    "feed_weight": weight,
                    "record_count": len(records),
                    "average_eggs": ChickenObservationsRepository._average_eggs(
                        records
                    ),
                    "average_laying_rate": ChickenObservationsRepository._average_rate(
                        records
                    ),
                    "min_date": records[0].recorded_date.isoformat(),
                    "max_date": records[-1].recorded_date.isoformat(),
                }
            )
        return summaries

    @staticmethod
    def _summarize_by_weather(ledgers):
        data_by_weather = {}
        for ledger in ledgers:
            key = ledger.weather_code.summary_code
            data_by_weather.setdefault(key, []).append(ledger)

        summaries = []
        for summary_code, records in sorted(data_by_weather.items()):
            first_record = records[0]
            summaries.append(
                {
                    "weather_code": summary_code,
                    "weather_name": first_record.weather_code.name,
                    "record_count": len(records),
                    "average_eggs": ChickenObservationsRepository._average_eggs(
                        records
                    ),
                    "average_laying_rate": ChickenObservationsRepository._average_rate(
                        records
                    ),
                }
            )
        return sorted(
            summaries,
            key=lambda summary: summary["record_count"],
            reverse=True,
        )

    @staticmethod
    def _average_eggs(records):
        egg_counts = [record.egg_count or 0 for record in records]
        return round(sum(egg_counts) / len(egg_counts), 1)

    @staticmethod
    def _average_rate(records):
        rates = [record.laying_rate() for record in records]
        return round(sum(rates) / len(rates), 1)

    @staticmethod
    def get_feed_group_laying_rates_table():
        """
        産卵率の時系列テーブルとフィードグループの絞り込み候補を返します。

        :return: {"feed_groups": ["Group Name"], "records": [{"date": "2023-10-01", "feed_group": "Group Name", "weather_code": "100", "laying_rate": 0.75}, ...]}
        """
        queryset = EggLedger.objects.select_related(
            "feed_group",
            "weather_code",
        ).order_by("recorded_date")

        feed_groups = []
        records = []
        for ledger in queryset:
            feed_group = str(ledger.feed_group)
            if feed_group not in feed_groups:
                feed_groups.append(feed_group)
            records.append(
                {
                    "date": ledger.recorded_date.isoformat(),
                    "feed_group": feed_group,
                    "weather_code": ledger.weather_code.summary_code,
                    "laying_rate": ledger.laying_rate(),
                }
            )

        return {
            "feed_groups": feed_groups,
            "records": records,
        }
