import random
import markdown
from datetime import datetime
from django.views.generic import TemplateView
from usa_research.domain.constants.almanac import MONTHLY_ANOMALIES, THEME_ANOMALIES
from usa_research.models import (
    MacroIndicator,
    RssFeed,
    SectorDailySnapshot,
    MsciCountryWeightReport,
    AssetPrice,
    Nasdaq100Company,
)


class IndexView(TemplateView):
    template_name = "usa_research/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # マクロ指標 (最新5日分)
        context["macro_indicators"] = MacroIndicator.objects.order_by("-date")[:5]

        # セクターローテーション計数表 (最新の日付のデータを取得)
        latest_snapshot = SectorDailySnapshot.objects.order_by("-date").first()
        if latest_snapshot:
            latest_date = latest_snapshot.date
            context["sector_snapshots"] = (
                SectorDailySnapshot.objects.filter(date=latest_date)
                .select_related("sector")
                .order_by("rank")
            )
            context["sector_latest_date"] = latest_date
        else:
            context["sector_snapshots"] = []

        # 季節系アノマリー
        context["monthly_anomalies"] = MONTHLY_ANOMALIES
        context["current_month"] = datetime.now().month

        # 業種・テーマ系アノマリー（ランダムに3枚選択）
        context["theme_anomalies"] = random.sample(
            THEME_ANOMALIES, min(len(THEME_ANOMALIES), 3)
        )

        # RSSフィードを取得 (最新20件)
        context["rss_feeds"] = RssFeed.objects.select_related("source").all()[:20]

        # MSCIレポートを取得 (最新1件)
        latest_report = MsciCountryWeightReport.objects.first()
        if latest_report:
            latest_report.summary_html = markdown.markdown(
                latest_report.summary_md, extensions=["extra", "tables"]
            )
            context["msci_report"] = latest_report

        # 資産クラスの長期推移
        # グラフ表示用にデータを取得。
        # 1950年からの日次データは膨大になるため、各月の月末データのみをサンプリングして取得する。
        from django.db.models import Max
        from django.db.models.functions import TruncMonth

        # 各月ごとの最大日付（月末営業日）を取得
        monthly_last_dates = (
            AssetPrice.objects.annotate(month=TruncMonth("date"))
            .values("month")
            .annotate(last_date=Max("date"))
            .values_list("last_date", flat=True)
        )

        # 月末データに絞って取得
        context["asset_prices"] = AssetPrice.objects.filter(
            date__in=monthly_last_dates
        ).order_by("date", "symbol")

        # NASDAQ100 銘柄リスト
        context["nasdaq100_companies"] = Nasdaq100Company.objects.all().order_by(
            "sector", "ticker"
        )

        return context
