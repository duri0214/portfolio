"""このファイル内に、必要なテーブルがすべて定義されます"""
from django.db import models
from django.contrib.auth import get_user_model


class Industry(models.Model):
    """
    viet-kabuで取得できる業種つき個社情報
    closing_price: 終値（千ドン）
    volume: 出来高（株）
    trade_price_of_a_day: 売買代金（千ドン）
    marketcap: 時価総額（億円）
    """
    market_code = models.CharField(max_length=4)
    symbol = models.CharField(max_length=10)
    company_name = models.CharField(max_length=50)
    industry1 = models.CharField(max_length=10)
    industry2 = models.CharField(max_length=20)
    open_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    high_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    low_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    closing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    volume = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    trade_price_of_a_day = models.DecimalField(max_digits=20, decimal_places=2, default=0.00)
    marketcap = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    per = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pub_date = models.DateField()


class IndClass(models.Model):
    """
    viet-kabuの産業名を産業区分1-3に
    """
    industry1 = models.CharField(max_length=10)
    industry_class = models.IntegerField()


class VnIndex(models.Model):
    """
    データ元:
    https://jp.investing.com/indices/vn-historical-data
    """
    Y = models.CharField(max_length=4)
    M = models.CharField(max_length=2)
    closing_price = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    pub_date = models.DateTimeField()


class WatchList(models.Model):
    """ウォッチリスト"""
    symbol = models.CharField(max_length=10)
    already_has = models.BooleanField(blank=True, null=True, default=1)
    bought_day = models.DateTimeField(blank=True, null=True)
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
    """SBI証券取り扱い銘柄"""
    market_code = models.CharField(max_length=4)
    symbol = models.CharField(max_length=10)


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
