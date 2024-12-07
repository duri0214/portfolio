from django.db.models import F, QuerySet

from vietnam_research.models import Industry, Market


class IndustryRepository:
    """
    このクラスは、 `Industry` Django モデルへのアクセスをカプセル化します。
    これにより、ビジネスロジックとデータアクセスロジックが切り離されます。

    Methods:
        get_industry_tickers: 特定の投資市場に関連する産業のシンボル（ティッカーコード）を取得します。
        get_symbol_details:  対象の投資市場で取扱いがあるシンボルの詳細情報を取得します。
    """

    @staticmethod
    def get_industry_tickers(markets: list[Market]) -> list[str]:
        """
        指定された投資市場に関連し、さらにSBI証券に存在する産業のシンボル（ティッカーコード）を取得します。

        Args:
            markets (list[Market]): シンボルを取得する投資市場 - Marketモデルオブジェクトのリスト。

        Returns:
            list[str]: 投資市場に関連し、かつSBI証券に存在する産業のシンボル（ティッカーコード）のリスト。
        """
        industry_records = (
            Industry.objects.filter(
                symbol__market__in=[market.id for market in markets]
            )
            .filter(symbol__sbi__isnull=False)
            .distinct()
            .values("symbol__code")
        )
        return [x["symbol__code"] for x in industry_records]

    @staticmethod
    def get_symbol_details(markets: list[Market]) -> QuerySet:
        """
        投資市場で取り扱われている、かつSBI証券に存在するシンボルの詳細情報を取得します。

        Args:
            markets (list[Market]): シンボルの詳細を取得する投資市場 - Marketモデルオブジェクトのリスト。

        Returns:
            QuerySet: 投資市場で取り扱われている、かつSBI証券に存在するシンボルの詳細情報。各シンボルの情報はディクショナリで、
            キーはシンボルに関連する各種情報を表すフィールド名、値はその情報です。
        """
        return (
            Industry.objects.filter(
                symbol__market__in=[market.id for market in markets]
            )
            .filter(symbol__sbi__isnull=False)
            .annotate(
                market_code=F("symbol__market__code"),
                symbol_code=F("symbol__code"),
            )
            .order_by(
                "symbol__ind_class__industry1",
                "symbol__ind_class__industry2",
                "symbol",
                "recorded_date",
            )
            .values(
                "symbol__ind_class__industry1",
                "symbol__ind_class__industry2",
                "market_code",
                "symbol_code",
                "recorded_date",
                "closing_price",
            )
        )
