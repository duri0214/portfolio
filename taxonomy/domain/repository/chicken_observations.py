from django.db.models import Sum, Count

from taxonomy.models import FeedWeight, EggLedger, HenGroup


class ChickenObservationsRepository:
    """
    FeedWeight, EggLedger, HenGroupを管理する
    鶏観察用のリポジトリクラス
    """

    # ------ 餌のデータ操作 ------
    @staticmethod
    def get_feed_usage_by_type():
        """
        餌の種類ごとの総投入量を取得
        :return: 餌の種類(name)ごとのweightの合計リスト
        """
        return (
            FeedWeight.objects.values("name")
            .annotate(total_weight=Sum("weight"))
            .order_by("-total_weight")
        )

    @staticmethod
    def get_feed_usage_over_time():
        """
        日ごとの餌の投入量を取得
        :return: 日付ごとの餌投入量のリスト
        """
        return (
            FeedWeight.objects.values("recorded_date", "name")
            .annotate(total_weight=Sum("weight"))
            .order_by("recorded_date")
        )

    @staticmethod
    def get_feed_efficiency():
        """
        餌の種類ごとの効率性（餌投入量と卵生産量の関係）
        :return: 餌ごとに関連するEggLedgerの生産数を含むデータ
        """
        return (
            FeedWeight.objects.values("name")
            .annotate(total_weight=Sum("weight"), total_eggs=Sum("eggledger__count"))
            .order_by("-total_eggs")
        )

    # ------ 卵生産データ操作 ------
    @staticmethod
    def get_egg_production_by_date():
        """
        日ごとの卵生産数を取得
        :return: 日ごとの卵記録数リスト
        """
        return (
            EggLedger.objects.values("recorded_date")
            .annotate(total_eggs=Count("id"))
            .order_by("recorded_date")
        )

    @staticmethod
    def get_egg_production_by_weather():
        """
        天気別の卵生産数を取得
        :return: 天気ごとの卵記録数リスト
        """
        return (
            EggLedger.objects.values("weather_code")
            .annotate(total_eggs=Count("id"))
            .order_by("-total_eggs")
        )

    @staticmethod
    def get_egg_production_trend():
        """
        日付＋天気での卵生産数（ヒートマップ用）
        :return: 天気と日付の組み合わせでの卵生産数リスト
        """
        return (
            EggLedger.objects.values("recorded_date", "weather_code")
            .annotate(total_eggs=Count("id"))
            .order_by("recorded_date", "weather_code")
        )

    # ------ 鶏グループのデータ操作 ------
    @staticmethod
    def get_hen_group_info():
        """
        鶏グループ情報を取得
        :return: HenGroupオブジェクトのリスト
        """
        return HenGroup.objects.all()

    @staticmethod
    def get_egg_count_by_group():
        """
        グループごとの卵数（1グループしかない場合でも利用）
        :return: HenGroupとその卵生産数
        """
        return HenGroup.objects.annotate(total_eggs=Count("eggledger")).first()
