from django.db.models import F, Value, CharField, Sum
from django.db.models import Max
from django.db.models.functions import Round, Concat
from django.db.models.query import QuerySet

from vietnam_research.models import Articles, BasicInformation, VnIndex, Uptrend
from vietnam_research.models import Industry, Watchlist


class MarketRepository:
    @staticmethod
    def get_articles(login_id):
        # TODO: 試作なのでデザインの都合上「投稿」は3つしか取得しない
        return (
            Articles.with_state(login_id)
            .annotate(user_name=F("user__email"))
            .order_by("-created_at")[:3]
        )

    @staticmethod
    def get_basic_info() -> QuerySet:
        return BasicInformation.objects.order_by("id").values("item", "description")

    @staticmethod
    def get_watchlist() -> QuerySet:
        """
        ウォッチリストを作成するためのクエリセットを作成します。

        closing_price: 終値は1,000VND単位なので、表示上は1,000を掛けている（1VND単位で表示）
        stocks_price_yen: VND→JPNへの変換は 200VND ≒ 1JPY
        buy_price_yen: 当初購入額（単価×購入株数）
        stocks_price_delta: 直近終値÷当初購入単価

        Returns:
            QuerySet: Watchlistをベースに換算額などの計算を組み合わせたもの
        """
        latest_date = Industry.objects.aggregate(Max("recorded_date"))[
            "recorded_date__max"
        ]

        return (
            Watchlist.objects.filter(already_has=1)
            .filter(symbol__industry__recorded_date=latest_date)
            .annotate(closing_price=Round(F("symbol__industry__closing_price") * 1000))
            .annotate(stocks_price_yen=F("stocks_price") / 200)
            .annotate(buy_price_yen=F("stocks_price_yen") * F("stocks_count"))
            .annotate(
                stocks_price_delta=Round(
                    (F("closing_price") / F("stocks_price") - 1) * 100, 2
                )
            )
        )

    @staticmethod
    def get_distinct_values(distinct_field: str) -> list:
        return [
            record[distinct_field]
            for record in VnIndex.objects.time_series_closing_price()
            .values(distinct_field)
            .distinct()
            .order_by(distinct_field)
        ]

    @staticmethod
    def get_vnindex_timeline() -> QuerySet:
        return VnIndex.objects.time_series_closing_price().order_by("Y", "M")

    @staticmethod
    def get_vnindex_at_year(year: str) -> list:
        return (
            VnIndex.objects.time_series_closing_price()
            .filter(Y=year)
            .order_by("Y", "M")
            .values("closing_price")
        )

    @staticmethod
    def get_industry_records_for(
        month: int, aggregate_field: str, aggregate_alias: str
    ) -> QuerySet:
        return (
            Industry.objects.filter(
                recorded_date=Industry.objects.slipped_month_end(
                    month
                ).formatted_recorded_date()
            )
            .annotate(
                ind_name=Concat(
                    F("symbol__ind_class__industry_class"),
                    Value("|"),
                    F("symbol__ind_class__industry1"),
                    output_field=CharField(),
                )
            )
            .values("ind_name")
            .annotate(**{aggregate_alias: Sum(aggregate_field)})
            .order_by("ind_name")
        )

    @staticmethod
    def get_denominator_for(month: int, denominator_field: str) -> float:
        end_of_month = Industry.objects.slipped_month_end(
            month
        ).formatted_recorded_date()
        records = Industry.objects.filter(recorded_date=end_of_month).values(
            denominator_field
        )
        return sum([record[denominator_field] for record in records])

    @staticmethod
    def get_annotated_uptrend():
        return (
            Uptrend.objects.prefetch_related("symbol", "ind_class")
            .annotate(
                industry1=F("symbol__ind_class__industry1"),
                industry_class=F("symbol__ind_class__industry_class"),
                ind_name=Concat(
                    F("symbol__ind_class__industry_class"),
                    Value("|"),
                    F("symbol__ind_class__industry1"),
                    output_field=CharField(),
                ),
                url_file_name=F("symbol__market__url_file_name"),
                code=F("symbol__code"),
            )
            .order_by(
                "symbol__ind_class__industry_class",
                "symbol__ind_class__industry1",
                "-stocks_price_delta",
            )
            .values(
                "industry1",
                "ind_name",
                "code",
                "url_file_name",
                "stocks_price_latest",
                "stocks_price_delta",
            )
        )

    @staticmethod
    def get_industry_names():
        return (
            Uptrend.objects.annotate(
                ind_name=Concat(
                    F("symbol__ind_class__industry_class"),
                    Value("|"),
                    F("symbol__ind_class__industry1"),
                    output_field=CharField(),
                )
            )
            .distinct()
            .order_by("ind_name")
            .values_list("ind_name", flat=True)
        )
