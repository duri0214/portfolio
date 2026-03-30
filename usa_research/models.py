from django.db import models


class RssSource(models.Model):
    name = models.CharField(max_length=100)
    url = models.URLField(unique=True)
    category = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    last_fetched_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name


class RssFeed(models.Model):
    source = models.ForeignKey(
        RssSource, on_delete=models.CASCADE, related_name="feeds"
    )
    title = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    link = models.URLField(max_length=500, unique=True)
    published_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.title


class Sector(models.Model):
    name = models.CharField(max_length=100)
    symbol = models.CharField(max_length=10)

    def __str__(self):
        return f"{self.name} ({self.symbol})"


class SectorDailySnapshot(models.Model):
    date = models.DateField()
    sector = models.ForeignKey(
        Sector, on_delete=models.CASCADE, related_name="snapshots"
    )
    rs_20d = models.FloatField()
    rs_slope_5d = models.FloatField()
    rank = models.IntegerField()
    rank_delta_5d = models.IntegerField()
    signal = models.CharField(max_length=10)

    class Meta:
        unique_together = ("date", "sector")
        ordering = ["-date", "rank"]

    def __str__(self):
        return f"{self.date} - {self.sector.name} - Rank: {self.rank}"


class MacroIndicator(models.Model):
    date = models.DateField(unique=True)

    ism_pmi = models.FloatField(null=True, blank=True)
    us_10y_yield = models.FloatField(null=True, blank=True)
    vix = models.FloatField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-date"]

    def __str__(self):
        return f"{self.date} - PMI: {self.ism_pmi}, 10Y: {self.us_10y_yield}, VIX: {self.vix}"


class MsciCountryWeightReport(models.Model):
    source = models.CharField(max_length=100, default="MSCI")
    report_date = models.DateField(unique=True)
    summary_md = models.TextField()
    pdf_url = models.URLField(max_length=500)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-report_date"]

    def __str__(self):
        return f"{self.report_date} - {self.source}"


class AssetPrice(models.Model):
    date = models.DateField()
    symbol = models.CharField(max_length=10)
    price = models.FloatField()  # 調整後終値 (Adjusted Close) を想定

    class Meta:
        unique_together = ("date", "symbol")
        ordering = ["-date", "symbol"]

    def __str__(self):
        return f"{self.date} - {self.symbol}: {self.price}"


class Nasdaq100Company(models.Model):
    ticker = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=200)
    sector = models.CharField(max_length=100)
    industry = models.CharField(max_length=100, blank=True)
    source = models.CharField(max_length=100)
    as_of = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["ticker"]

    def __str__(self):
        return f"{self.ticker} - {self.name}"


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
    NASDAQ などの米国株が主な対象です。

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
    ticker = models.CharField(max_length=10, verbose_name="ティッカー")
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

    class Meta:
        ordering = ["-recorded_date", "ticker"]
