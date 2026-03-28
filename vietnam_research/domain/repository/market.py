from django.db.models import F, Value, CharField, Sum
from django.db.models import Max
from django.db.models.functions import Round, Concat
from django.db.models.query import QuerySet

from vietnam_research.models import (
    Articles,
    BasicInformation,
    VnIndex,
    Uptrend,
    VietnamStatistics,
)
from vietnam_research.models import Industry, Watchlist


class MarketRepository:
    """
    マーケット情報のリポジトリクラス。
    記事、基本情報、ウォッチリスト、VN-INDEX、統計データなどのDB操作・集計を担当します。
    """

    @staticmethod
    def articles(login_id):
        """
        ダッシュボード表示用の記事（みんなの意見）を取得します。

        Args:
            login_id (int or None): ログインユーザーのID（未ログイン時はNone）
                                   いいね済みかどうかの状態判定に使用されます。

        Returns:
            QuerySet: 最新の6件の記事。
            アノテーションにより以下のフィールドが含まれます：
                - user_name: 投稿者のメールアドレス (user__email)
                - is_liked: ログインユーザーがいいね済みかどうか (Articles.with_state による)
                - like_count: 記事のいいね数 (Articles.with_state による)
        """
        return (
            Articles.with_state(login_id)
            .annotate(user_name=F("user__email"))
            .order_by("-created_at")[:6]
        )

    @staticmethod
    def basic_info() -> QuerySet:
        """
        ベトナムの基本経済指標を取得します。

        Returns:
            QuerySet: 項目名（item）と内容（description）のセット。
        """
        return BasicInformation.objects.order_by("id").values("item", "description")

    @staticmethod
    def watchlist() -> QuerySet:
        """
        保有銘柄の時価換算や損益を計算したウォッチリストを取得します。

        - 1,000VND単位の終値を1VND単位に換算
        - VNDからJPYへの簡易換算（200VND = 1JPY）
        - 取得単価に対する騰落率（stocks_price_delta）の算出

        Returns:
            QuerySet: すでに保有している銘柄（already_has=1）のリスト。
            以下のフィールドがアノテーションされます：
                - closing_price: 現在の終値 (1VND単位)
                - stocks_price_yen: 取得単価 (日本円換算)
                - buy_price_yen: 当初購入額 (単価×購入株数、日本円換算)
                - stocks_price_delta: 取得単価に対する騰落率 (%)
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
    def distinct_values(distinct_field: str) -> list:
        """指定されたフィールドの重複しない値の一覧を取得します。"""
        return [
            record[distinct_field]
            for record in VnIndex.objects.time_series_closing_price()
            .values(distinct_field)
            .distinct()
            .order_by(distinct_field)
        ]

    @staticmethod
    def vnindex_timeline() -> QuerySet:
        """VN-INDEXの時系列データを取得します。"""
        return VnIndex.objects.time_series_closing_price().order_by("Y", "M")

    @staticmethod
    def vnindex_at_year(year: str) -> list:
        """指定された年のVN-INDEX時系列データを取得します。"""
        return (
            VnIndex.objects.time_series_closing_price()
            .filter(Y=year)
            .order_by("Y", "M")
            .values("closing_price")
        )

    @staticmethod
    def iip_timeline() -> QuerySet:
        """IIP（鉱工業生産指数）の時系列データを取得します。"""
        return VietnamStatistics.objects.filter(
            element="industrial production index"
        ).order_by("period")

    @staticmethod
    def cpi_timeline() -> QuerySet:
        """CPI（消費者物価指数）の時系列データを取得します。"""
        return VietnamStatistics.objects.filter(
            element="consumer price index"
        ).order_by("period")

    @staticmethod
    def industry_records_for(
        month: int, aggregate_field: str, aggregate_alias: str
    ) -> QuerySet:
        """
        指定された月（現在からXヶ月前）の業種別集計データを取得します。
        主にレーダーチャート（業種別マクロ分析）の各項目の構成比（分子）を計算するために使用されます。

        業種クラス（ind_class）が定義されていないシンボルは、正確な比率を算出する際のノイズとなるため
        symbol__ind_class__isnull=False で明示的に除外しています。

        Args:
            month (int): 何ヶ月前の月末データを取得するか（0: 当月末, 1: 先月末 ...）
            aggregate_field (str): 集計対象のフィールド名（例: 'stocks_count', 'stocks_price'）
            aggregate_alias (str): 集計結果に付与するエイリアス名

        Returns:
            QuerySet: 業種名（ind_name）でグループ化され、指定されたフィールドが合計された結果
        """
        return (
            Industry.objects.filter(
                recorded_date=Industry.objects.slipped_month_end(
                    month
                ).formatted_recorded_date(),
                symbol__ind_class__isnull=False,
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
    def sum_of_industry_field_for(month: int, aggregate_field: str) -> float:
        """
        指定された月（現在からXヶ月前）の全業種合計値を算出します。
        レーダーチャート（業種別マクロ分析）の構成比を計算する際の「分母」として使用します。

        分子側（industry_records_for）と母集団を一致させるため、
        業種クラス（ind_class）が定義されていないシンボルは集計から除外しています。

        Args:
            month (int): 何ヶ月前の月末データを計算するか
            aggregate_field (str): 合計を算出する対象のフィールド名

        Returns:
            float: 指定された月の全業種の合計値
        """
        # 指定された月（過去Xヶ月前）の月末日付を取得
        target_date = Industry.objects.slipped_month_end(
            month
        ).formatted_recorded_date()

        # 指定された日付のレコードで、業種が定義されており、かつ集計対象の数値が null でないものを抽出
        valid_industry_records = Industry.objects.filter(
            recorded_date=target_date,
            symbol__ind_class__isnull=False,
            **{f"{aggregate_field}__isnull": False},
        )

        # 集計対象のフィールド値のみを取得し、その合計を算出
        values_to_sum = valid_industry_records.values_list(aggregate_field, flat=True)

        return sum(values_to_sum)

    @staticmethod
    def annotated_uptrend():
        """
        上昇トレンド銘柄（傾き判定）の一覧を加工して取得します。

        - 銘柄コード、業種名（大分類|小分類）、市場別のURLファイル名を付与
        - 業種ごとにグループ化し、その中で上昇率（stocks_price_delta）の降順でソート

        Returns:
            QuerySet: 業種別の詳細データを含むトレンド銘柄リスト。
            以下のフィールドが含まれます：
                - industry1: 業種 (小分類)
                - industry_class: 業種 (大分類)
                - ind_name: 業種名 (大分類|小分類)
                - url_file_name: チャート表示用のURLファイル名 (symbol__market__url_file_name)
                - code: 銘柄コード (symbol__code)
                - stocks_price_latest: 最新株価
                - stocks_price_delta: 騰落率 (傾き)
        """
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
    def industry_names():
        """
        上昇トレンド銘柄が存在する業種名（大分類|小分類）のユニークな一覧を取得します。

        Returns:
            list: 業種名のリスト（ソート済み）。
            アノテーション `ind_name` (大分類|小分類) のリストが返ります。
        """
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
