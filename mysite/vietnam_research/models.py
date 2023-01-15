"""このファイル内に、必要なテーブルがすべて定義されます"""
import datetime

from dateutil.relativedelta import relativedelta
from django.db import models
from django.contrib.auth import get_user_model
from django.db.models import QuerySet


class Market(models.Model):
    """
    マーケットマスタ

    code: ホーチミンなら「HOSE」\n
    market_name: ホーチミンなら「ホーチミン証券取引所」\n
    url_file_name: ホーチミンなら「hcm」

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=50)
    url_file_name = models.CharField(max_length=10, null=True)

    class Meta:
        db_table = 'vietnam_research_m_market'


class Symbol(models.Model):
    """
    シンボルマスタ

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """
    code = models.CharField(max_length=10)
    name = models.CharField(max_length=50)
    market = models.ForeignKey(Market, on_delete=models.CASCADE)

    class Meta:
        db_table = 'vietnam_research_m_symbol'

    def __str__(self):
        return f"{self.market.name}｜{self.code}｜{self.name}"


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

    class Meta:
        db_table = 'vietnam_research_m_industry_class'


class IndustryQuerySet(models.QuerySet):
    def slipped_month_end(self, month_shift: int, base_date=datetime.datetime.today()) -> QuerySet:
        """
        Xヶ月前の、（Industryにデータが存在する）月末日のレコードを取得する

        Args:
            month_shift: シフトしたい月数 e.g. -3
            base_date: 基準日

        Returns:
            QuerySet: 基準日が 2021-10-24 のとき、シフトしたい月数を -3 と指定すると 2021-07-30
        """
        slipped_date = base_date + relativedelta(months=month_shift, day=31)

        return self \
            .filter(recorded_date__year=slipped_date.year, recorded_date__month=slipped_date.month) \
            .order_by('recorded_date')\
            .latest('recorded_date')


class Industry(models.Model):
    """
    viet-kabuで取得できる業種つき個社情報\n
    recorded_date: 計上日\n
    closing_price: 終値（千ドン）\n
    volume: 出来高（株）\n
    trade_price_of_a_day: 売買代金（千ドン）\n
    marketcap: 時価総額（億円）\n
    TODO: decimalじゃなくてfloatでいいのでは？

    See Also: https://www.viet-kabu.com/stock/hcm.html
    """
    recorded_date = models.DateField()
    market = models.ForeignKey(Market, on_delete=models.CASCADE)
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    ind_class = models.ForeignKey(IndClass, on_delete=models.CASCADE)
    open_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    high_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    low_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    closing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    volume = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    trade_price_of_a_day = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    marketcap = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    per = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = IndustryQuerySet.as_manager()

    def formatted_recorded_date(self, format_at='%Y-%m-%d') -> str:
        """
        指定した書式で recorded_date を返す

        Args:
            format_at: 出力時の書式 %Y-%m-%d

        Returns:
            datetime.date(2022, 10, 28) なら 2022-10-28
        """
        return self.recorded_date.strftime(format_at)


class VnIndexQuerySet(models.QuerySet):
    def time_series_closing_price(self) -> QuerySet:
        return self.order_by('Y', 'M').values('Y', 'M', 'closing_price').distinct()


class VnIndex(models.Model):
    """
    ベトナムの世界での日経平均のような数字

    TODO: decimalじゃなくてfloatでいいのでは？\n
    See Also: https://jp.investing.com/indices/vn-historical-data
    """
    Y = models.CharField(max_length=4)
    M = models.CharField(max_length=2)
    closing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    objects = VnIndexQuerySet.as_manager()


class Watchlist(models.Model):
    """ウォッチリスト"""
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    symbol = models.ForeignKey(Symbol, on_delete=models.CASCADE)
    already_has = models.BooleanField(blank=True, null=True, default=1)
    bought_day = models.DateField(blank=True, null=True)
    stocks_price = models.PositiveIntegerField(blank=True, null=True, default=0)
    stocks_count = models.IntegerField(blank=True, null=True, default=0)


class DailyTop5(models.Model):
    """日次Top5"""
    ind_name = models.CharField(max_length=10)
    market_code = models.CharField(max_length=4)
    symbol = models.CharField(max_length=10)
    trade_price_of_a_day = models.FloatField(default=0.00)
    per = models.FloatField(default=0.00)


class DailyUptrends(models.Model):
    """日次Uptrends（傾き計算考慮）"""
    ind_name = models.CharField(max_length=10)
    market_code = models.CharField(max_length=4)
    symbol = models.CharField(max_length=10)
    stocks_price_oldest = models.FloatField()
    stocks_price_latest = models.FloatField()
    stocks_price_delta = models.FloatField()


class Sbi(models.Model):
    """
    SBI証券取り扱い銘柄

    See Also: https://search.sbisec.co.jp/v2/popwin/info/stock/pop6040_usequity_list.html
    """
    market_code = models.CharField(max_length=4)
    symbol = models.CharField(max_length=10)

    class Meta:
        db_table = 'vietnam_research_m_sbi'


class BasicInformation(models.Model):
    """基本情報"""
    item = models.TextField()
    description = models.TextField(blank=True, null=True)


class Articles(models.Model):
    """記事"""
    title = models.CharField(verbose_name='タイトル', max_length=200)
    note = models.TextField(verbose_name='投稿内容')
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField('公開日時', auto_now_add=True)


class Likes(models.Model):
    """いいね"""
    articles = models.ForeignKey('Articles', on_delete=models.CASCADE)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)


class Unit(models.Model):
    """財務単位"""
    name = models.CharField(max_length=10)

    def __str__(self):
        return '%s' % self.name


class FinancialResultWatch(models.Model):
    """決算ウォッチ"""
    date = models.DateField()
    ticker = models.CharField(max_length=10)
    quarter = models.IntegerField()
    eps_ok = models.BooleanField(null=True)
    sales_ok = models.BooleanField(null=True)
    guidance_ok = models.BooleanField(null=True)
    eps_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='r_eps_unit')
    eps_estimate = models.FloatField(default=0.00)
    eps_actual = models.FloatField(default=0.00)
    sales_unit = models.ForeignKey(Unit, on_delete=models.CASCADE, related_name='r_sales_unit')
    sales_estimate = models.FloatField(default=0.00)
    sales_actual = models.FloatField(default=0.00)
    y_over_y_growth_rate = models.FloatField(default=0.00)
    note_url = models.URLField(null=True)
    user = models.ForeignKey(get_user_model(), on_delete=models.CASCADE)
