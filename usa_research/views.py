import random
from datetime import datetime
from django.views.generic import TemplateView
from usa_research.domain.constants.almanac import MONTHLY_ANOMALIES, THEME_ANOMALIES
from usa_research.models import RssFeed


class IndexView(TemplateView):
    template_name = "usa_research/index.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

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
