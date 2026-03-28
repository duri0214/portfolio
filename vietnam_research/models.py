import datetime

from dateutil.relativedelta import relativedelta
from django.contrib.auth import get_user_model
from django.db import models
from django.db.models import QuerySet, IntegerField, Case, Count, When


class Market(models.Model):
    """
    マーケットマスタ

    code: ホーチミンなら「HOSE」\n
    market_name: ホーチミンなら「ホーチミン証券取引所」\n
    url_file_name: ホーチミンなら「hcm」

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """

    code = models.CharField(max_length=20)
    name = models.CharField(max_length=50)
    url_file_name = models.CharField(max_length=10, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class IndClass(models.Model):
    """
    viet-kabuの産業を、1次産業（例: 農業）、2次産業（例: 製造業）、3次産業（サービス業）にカテゴライズする

    industry1: サイゴンビールなら、製造業
    industry2: サイゴンビールなら、食品・飲料
    industry_class: サイゴンビールなら、2（加工業）

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """

    industry1 = models.CharField(max_length=10)
    industry2 = models.CharField(max_length=20)
    industry_class = models.IntegerField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    class Meta:
        unique_together = (("industry1", "industry2"),)


class Symbol(models.Model):
    """
    シンボルマスタ

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """

    code = models.CharField(max_length=10)
    name = models.CharField(max_length=255)
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    ind_class = models.ForeignKey(IndClass, on_delete=models.CASCADE, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["code", "market_id"], name="code_market_id_unique"
            )
        ]

    def __str__(self):
        return f"{self.market.name}｜{self.code}｜{self.name}"


class IndustryQuerySet(models.QuerySet):
    """業種データのQuerySet拡張"""

    def slipped_month_end(
        self, month_shift: int, base_date=datetime.datetime.today()
    ) -> QuerySet:
        """
        Xヶ月前の、（Industryにデータが存在する）月末日のレコードを取得する

        Args:
            month_shift: シフトしたい月数 e.g. -3
            base_date: 基準日

        Returns:
            QuerySet: 基準日が 2021-10-24 のとき、シフトしたい月数を -3 と指定すると 2021-07-30
        """
        slipped_date = base_date + relativedelta(months=month_shift, day=31)

        return (
            self.filter(
                recorded_date__year=slipped_date.year,
                recorded_date__month=slipped_date.month,
            )
            .order_by("recorded_date")
            .latest("recorded_date")
        )


class Industry(models.Model):
    """
    viet-kabuで取得できる業種つき個社情報\n
    recorded_date: 計上日\n
    closing_price: 終値（千ドン）\n
    volume: 出来高（株）\n
    marketcap: 時価総額（億円）\n

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """

    recorded_date = models.DateField()
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    open_price = models.FloatField(null=True)
    high_price = models.FloatField(null=True)
    low_price = models.FloatField(null=True)
    closing_price = models.FloatField(null=True)
    volume = models.FloatField(null=True)
    marketcap = models.FloatField(null=True)
    per = models.FloatField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = IndustryQuerySet.as_manager()

    def formatted_recorded_date(self, format_at="%Y-%m-%d") -> str:
        """
        指定した書式で recorded_date を返す

        Args:
            format_at: 出力時の書式 %Y-%m-%d

        Returns:
            datetime.date(2022, 10, 28) なら 2022-10-28
        """
        return self.recorded_date.strftime(format_at)


class VnIndexQuerySet(models.QuerySet):
    """VN-INDEXデータのQuerySet拡張"""

    def time_series_closing_price(self) -> QuerySet:
        """時系列の終値データを取得します。"""
        return self.order_by("Y", "M").values("Y", "M", "closing_price").distinct()


class VnIndex(models.Model):
    """
    ベトナムの世界での日経平均のような数字

    See Also: https://jp.investing.com/indices/vn-historical-data
    """

    Y = models.CharField(max_length=4)
    M = models.CharField(max_length=2)
    closing_price = models.FloatField()

    objects = VnIndexQuerySet.as_manager()

    class Meta:
        constraints = [models.UniqueConstraint(fields=["Y", "M"], name="y_m_unique")]


class Watchlist(models.Model):
    """
    ウォッチリスト銘柄
    ユーザーが注目している銘柄や保有している銘柄の情報を管理します。
    """

    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    symbol = models.ForeignKey(
        Symbol, on_delete=models.CASCADE, verbose_name="シンボル"
    )
    already_has = models.BooleanField(
        verbose_name="保有済み", blank=True, null=True, default=1
    )
    bought_day = models.DateField(verbose_name="購入日", blank=True, null=True)
    stocks_price = models.PositiveIntegerField(
        verbose_name="購入価格", blank=True, null=True, default=0
    )
    stocks_count = models.IntegerField(
        verbose_name="数量", blank=True, null=True, default=0
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["user", "symbol"], name="user_symbol_unique"
            )
        ]


class Uptrend(models.Model):
    """
    トレンド銘柄（上昇傾向）
    日次バッチで計算された銘柄ごとの価格変化情報を保持します。
    stocks_price_delta: 14日前（またはデータのある最古の日）からの変化率(%)
    """

    stocks_price_oldest = models.FloatField()
    stocks_price_latest = models.FloatField()
    stocks_price_delta = models.FloatField()
    symbol = models.ForeignKey(Symbol, on_delete=models.SET_NULL, null=True)


class Sbi(models.Model):
    """
    SBI証券取り扱い銘柄

    See Also: https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_vn_list.html
    See Also: https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_usequity_list.html
    """

    symbol = models.ForeignKey(Symbol, on_delete=models.SET_NULL, null=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class BasicInformation(models.Model):
    """
    ベトナム基本情報
    面積、人口、GDPなどの基礎的な経済・社会指標を保持します。

    See Also: https://www.jetro.go.jp/world/asia/vn/basic_01.html
    """

    item = models.TextField()
    description = models.TextField(blank=True, null=True)


class Articles(models.Model):
    """
    ユーザー投稿記事
    市場分析や銘柄考察など、ユーザーが投稿したコンテンツを保持します。
    いいね！機能に対応しています。
    """

    title = models.CharField(verbose_name="タイトル", max_length=200)
    note = models.TextField(verbose_name="投稿内容")
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField("公開日時", auto_now_add=True)

    @staticmethod
    def with_state(user_id: int) -> QuerySet:
        """
        指定したユーザーの「いいね！」状態を含めた記事一覧を取得します。
        """
        return Articles.objects.annotate(
            likes_cnt=Count("likes"),
            liked_by_me=Case(
                When(
                    id__in=Likes.objects.filter(user_id=user_id).values("articles_id"),
                    then=1,
                ),
                default=0,
                output_field=IntegerField(),
            ),
        )


class Likes(models.Model):
    """
    記事に対する「いいね！」
    ユーザーと記事の紐付けを管理します。
    """

    articles = models.ForeignKey("Articles", on_delete=models.CASCADE)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["articles_id", "user_id"], name="articles_user_unique"
            )
        ]


class Unit(models.Model):
    """財務単位"""

    name = models.CharField(max_length=10)

    def __str__(self):
        return self.name

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(null=True)


class FinancialResultWatch(models.Model):
    """
    決算ウォッチ
    各銘柄の四半期ごとの決算発表結果（予想 vs 実績）を保持します。
    ※本機能は usa_research アプリ作成前の暫定的な配置であり、主な対象は NASDAQ などの米国株です。

    recorded_date: Note公開日
    """

    recorded_date = models.DateField(verbose_name="Note公開日")
    quarter = models.SmallIntegerField(verbose_name="四半期")
    eps_ok = models.BooleanField(verbose_name="EPS達成", null=True)
    sales_ok = models.BooleanField(verbose_name="売上達成", null=True)
    guidance_ok = models.BooleanField(verbose_name="ガイダンス達成", null=True)
    eps_estimate = models.FloatField(verbose_name="EPS予想")
    eps_actual = models.FloatField(verbose_name="EPS実績")
    sales_estimate = models.FloatField(verbose_name="売上予想")
    sales_actual = models.FloatField(verbose_name="売上実績")
    y_over_y_growth_rate = models.FloatField(verbose_name="前年同期比(%)")
    note_url = models.URLField(verbose_name="NoteURL", null=True, blank=True)
    symbol = models.ForeignKey(
        Symbol, on_delete=models.SET_NULL, null=True, verbose_name="シンボル"
    )
    eps_unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="r_eps_unit",
        verbose_name="EPS単位",
    )
    sales_unit = models.ForeignKey(
        Unit,
        on_delete=models.CASCADE,
        related_name="r_sales_unit",
        verbose_name="売上単位",
    )


class FaoFoodBalanceRankers(models.Model):
    """
    FAO食品バランス統計
    国別の水産物などの供給量ランキングデータを保持します。
    """

    year = models.PositiveIntegerField()
    rank = models.PositiveIntegerField()
    name = models.CharField(max_length=255)
    item = models.CharField(max_length=255)
    element = models.CharField(max_length=255)
    unit = models.CharField(max_length=255)
    value = models.FloatField()


class VietnamStatistics(models.Model):
    """
    ベトナム統計データ
    IIP（鉱工業生産指数）やCPI（消費者物価指数）などの時系列統計を保持します。
    """

    element = models.CharField(max_length=255)
    period = models.DateField()
    value = models.FloatField()


class ExchangeRate(models.Model):
    """
    為替レート
    通貨ペアごとの最新レートを保持します。
    """

    base_cur_code = models.CharField(max_length=3)
    dest_cur_code = models.CharField(max_length=3)
    rate = models.FloatField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
