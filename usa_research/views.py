import random
from datetime import datetime
from django.views.generic import TemplateView
from usa_research.domain.constants.almanac import MONTHLY_ANOMALIES, THEME_ANOMALIES
from usa_research.models import MacroIndicator, RssFeed, SectorDailySnapshot


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

        return context
